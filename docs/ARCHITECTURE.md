# Architecture

## The pipeline

Five stages. Each writes files; each is resumable; each can be re-run
independently. Nothing holds state in memory across items.

```
 1. EXTRACT     extract_words.py    .xlsx ──────────► words.json          (1112 words, groups 1-38)
 2. CARDS       generate.py         words.json ─────► cards/<word>.json   (1 file per word)
 3. GROUPS      group.py            cards/ ─────────► groups/<kind>/*.json (655 groups, 7 kinds)
 4. BANK        quizgen.py          cards/+groups/ ─► bank/<unit>.json    (2010 questions)
 5. RENDER      render.py           cards/+groups/ ─► out/group_NN.md
                group.py render     groups/ ────────► out/groups.md
                build_app.py        all three ──────► out/flashcards.html
                export_anki.py      cards/+groups/ ─► out/anki.tsv
```

Deployment is downstream of stage 5 and fully automatic:

```
 git push ──► GitHub Pages rebuild        (serves index.html + out/)
          └─► .github/workflows/android.yml
                 triggers only on out/flashcards.html or android/ changing
                 copies the HTML into android/app/src/main/assets/
                 builds, signs, publishes a release
                 => /releases/latest/download/gre-vocab.apk  (stable URL)
```

---

## Stage 2 — cards

`cardspec.py` is the contract. It holds `CARD_SCHEMA` and
`build_system_prompt()`, which assembles the frozen prompt from `skill/SKILL.md`
plus `skill/reference/exemplar-censor.md` plus an output contract.

Determinism matters here for a specific reason: the prompt is the **cache
prefix**. Same bytes on every call means the server-side prompt cache hits, which
took cost from $0.27/card cold to ~$0.08 warm. Anything non-deterministic in that
function — a timestamp, a UUID, an unsorted dict — silently destroys that.

`generate.py` runs one warm-up call alone before parallelising, so six cold calls
do not all pay full price for the prefix.

Selection flags: `--limit`, `--only <words>`, `--force`, and `--null-field
<field>` which re-runs only cards whose field is null. That last one exists
because after a skill fix you usually want to retry only the items the fix could
possibly change.

---

## Stage 3 — groups

Seven grouping kinds. **Two are computed with no model at all** — `root` and
`confusables` were put on every card at schema-design time precisely so these
would fall out as graph problems later.

| kind | count | how |
|---|---|---|
| `root` | 51 | group by normalised `root` field |
| `lookalike` | 37 | connected components over **mutual** `confusables` edges |
| `meaning` | 250 | model discovery |
| `intensity` | 108 | model discovery, `words` array is ordered weak → strong |
| `antonym` | 100 | model discovery |
| `connotation` | 74 | model discovery |
| `second-meaning` | 35 | model discovery |

**The mutual-edge rule is important.** Confusability is not transitive. Following
one-way edges collapsed 234 words into a single meaningless component, because
*abstain → abstruse → abstract* chains on forever. Requiring both words to name
each other cut 744 directed edges to 192 mutual ones and produced clean
components of 3–7. Do not "improve" this back into a transitive closure.

Three sub-stages, run in order:

```
python group.py mechanical   # root + lookalike, deterministic, free
python group.py discover     # 5 model calls, each seeing all 1112 words
python group.py write        # one independent call per group
python group.py render       # -> out/groups.md
```

Discovery and write-up are split deliberately. Discovery sees the whole index at
once and returns only membership lists, which is cheap. The write-up is then one
stateless call per group, so 655 sections are written to the same standard rather
than degrading down one enormous response.

The write-up prompt enforces one rule that does the real work: **a word's nuance
must contrast, not re-define.** If a line could be pasted under a different word
in the same group, it is too vague.

---

## Stage 4 — the question bank

Generates the two exam formats templates cannot produce, plus fresh cloze
contexts.

**Generation targets the GregMat groups (1–38), not the semantic ones.** Those
are the owner's actual study unit — "quiz Group 7" is a real thing they want to
do. But GregMat groups are arbitrary batches, so a Sentence Equivalence item
cannot find its second correct answer inside one.

The resolution is that the two grouping systems do different jobs:

- the **GregMat group** picks *what to test* (the target word)
- the **semantic groups** supply *what to test it against* (distractors, and the
  co-answer for Sentence Equivalence)

`semantic_neighbours()` in `quizgen.py` is what bridges them.

Then every question is **blind re-solved** by an independent call, as described
in PHILOSOPHY § 5. About 10% are rejected; rejects are recorded in the batch file
rather than discarded, so you can see what the check is catching.

---

## The transport layer

`claude_cli.py` is the single path to the model, shared by `generate.py`,
`group.py` and `quizgen.py`. Three details in it are hard-won and must not be
casually changed:

**1. Invoke `bin/claude.exe` directly, not `claude.cmd`.** The `.cmd` shim routes
through `cmd.exe`, which caps the command line at 8,191 characters. The system
prompt alone is ~13,000. The native binary gets the 32,767 `CreateProcess` limit.

**2. The user prompt goes on stdin, not argv.** This removes the 32,767 ceiling
entirely — verified at 42,000 characters. It is what lets a whole 148,000-character
word index go into a single discovery call. Only the system prompt and schema
ride on the command line.

**3. `--exclude-dynamic-system-prompt-sections`.** Keeps cwd, environment and git
status out of the prompt, so the cached prefix stays byte-stable.

Output is constrained by `--json-schema`, so a malformed response is structurally
impossible rather than something the linter has to catch afterwards.

---

## The client app

`build_app.py` emits `out/flashcards.html`: one file, ~5.7 MB, no server, no
network, no framework, no build step. Card, group and bank data are embedded as
JSON literals at build time, which is what makes it work over `file://` and
inside a WebView.

Four modes, all sharing one hash router:

- **Browse** — every word, searchable across meaning, root and sense tags
- **Drill** — flashcards with `space` to reveal, `1`/`2`/`3` to mark
- **Quiz** — nine question types over an SM-2 scheduler
- **Groups** — all 655 groups; every card links to the ones it belongs to

### Question types

Six are generated client-side from data already present, and are therefore always
correct by construction:

| type | source |
|---|---|
| `cloze` | a card's own sentence with the word blanked, distractors from its cluster |
| `nuance` | a group write-up's nuance line, word masked |
| `odd` | four from a cluster plus an intruder |
| `strongest` | top of an intensity scale |
| `connotation` | positive / neutral / negative |
| `recall` | type the word from its gloss |

Three come from the verified bank: `tc2`, `se`, `fresh`.

**Distractor selection is tiered, and the tiers must be exhausted in order:** the
group being quizzed, then any group the word belongs to, then random. An earlier
version added scoped words to a pool and then shuffled the whole pool together,
which let a random word beat an in-cluster one — precisely what makes a question
too easy.

### Android

`android/` is a thin WebView shell. Two details are load-bearing:

**Assets are served through `WebViewAssetLoader` on an `https://` origin**, not
loaded as `file:///android_asset/`. `localStorage` on a `file://` origin is
unreliable across WebView versions, and `localStorage` holds the user's progress.

**Export goes through a JS bridge.** A `blob:` download inside a WebView is
silently dropped by DownloadManager, so Export would have appeared to work and
produced nothing. The web build calls `AndroidBridge.saveText` when present and
falls back to a blob elsewhere.

`minSdk 26`, `targetSdk 35` (Android 15). No permissions — the app never touches
the network.
