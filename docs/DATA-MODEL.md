# Data model

Every schema here is authoritative. Where a Python definition exists, that
definition wins and this document is a description of it.

---

## `words.json` — the input list

```json
[ { "word": "abound", "groups": [1] }, ... ]
```

1,112 unique words. `groups` are **GregMat group numbers 1–38**, the owner's
study batches. A word can appear in more than one. Produced by
`extract_words.py`, which scans the source spreadsheet for `Group N` headers and
reads downward — the sheet is a grid with groups in column pairs wrapping into
horizontal bands, not a table.

The source `.xlsx` is gitignored (GregMat's paid product).

> Naming collision to keep straight: **"group" means two different things.**
> GregMat groups 1–38 (`c.groups`, study batches) and semantic groups
> (`groups/<kind>/*.json`, 655 meaning clusters). They are unrelated and do
> different jobs. See ARCHITECTURE § Stage 4.

---

## `cards/<slug>.json` — one per word

Defined by `CARD_SCHEMA` in `cardspec.py`. All 18 keys are **required to be
present**; the nullable ones may be `null`. Filename slug: lowercase, non-alphanumerics
to `_` (`ad hoc` → `ad_hoc.json`).

### Prose fields — rendered on the card

| field | null? | notes |
|---|---|---|
| `word` | no | |
| `pos` | no | `"adj."`, `"v. / n."` |
| `pron` | no | respelling, CAPS on the stressed syllable: `WIL-fuhl` |
| `pron_note` | **yes** | variant spelling or a real mispronunciation trap |
| `means` | no | markdown; definition then nuance. The most important field. |
| `trap` | **yes** | ONE near-identical false friend (censor/censure). Never a list. |
| `trick_line` | **yes** | one-line mnemonic, rendered as a blockquote |
| `trick_unpack` | **yes** | exactly one sentence; null iff `trick_line` is null |
| `sentences` | no | exactly 2, varied register, word bolded with `**` |
| `in_the_wild` | **yes** | one genuine pop-culture / daily-life hook |
| `etymology` | **yes** | only when the root genuinely aids memory |

The `**bold**` markers in `sentences` are **load-bearing**, not decoration: the
cloze generator finds the blank by regex on them, and the linter uses them to
verify irregular inflections.

### Machine fields — drive grouping, search and quizzes

| field | type | purpose |
|---|---|---|
| `one_line` | string | ≤14 words. Browse list, quiz prompts, discovery index. |
| `root` | string\|null | `"cor, cordis (heart)"` — normalised to build root families |
| `root_family` | string[] | other English words from the root |
| `confusables` | string[] | genuine sound/spelling confusables — **mutual** edges build lookalike clusters |
| `sense_tags` | string[] | 2–5 lowercase concept tags, seeds meaning clusters |
| `register` | enum | formal / neutral / informal / literary / technical / legal |
| `connotation` | enum | positive / neutral / negative / depends |

Added at save time, not by the model: `groups` (GregMat numbers).

---

## `groups/<kind>/<id>.json`

`kind` ∈ `meaning`, `lookalike`, `second-meaning`, `intensity`, `connotation`,
`antonym`, `root`.

```json
{
  "kind": "meaning",
  "id": "meaning__dull-and-unimaginative",
  "title": "Dull and unimaginative",
  "seed_words": ["prosaic", "pedestrian", "insipid", "vapid"],
  "core": "markdown - the meaning they all share",
  "words": [ { "word": "prosaic", "nuance": "how THIS word differs from the others" } ],
  "exam_note": "one line on how the GRE exploits this group, or null"
}
```

- `id` is the filename stem and is the **anchor** used by cross-links in
  `out/groups.md`. It is used rather than the title because titles collide across
  kinds — "Deception" exists as both a meaning cluster and a connotation group.
- For `kind: "intensity"` the **order of `words` is meaningful** (weakest first).
  The `strongest` quiz type depends on it.
- A group with `core` unset was discovered but not yet written up; renderers and
  the app filter those out.

---

## `bank/<unit>.json` — quiz questions

Unit id: `gregmat<NN>__b<batch>`.

```json
{
  "unit": "gregmat01__b0",
  "gregmat_group": 1,
  "words": ["abound", "amorphous", "austere", "belie"],
  "questions": [ { ... } ],
  "rejects":   [ { "why": "...", "problem": "...", "stem": "..." } ]
}
```

A question:

```json
{
  "id": "gregmat01__b0__tc2__03",
  "type": "tc2",
  "stem": "Though ... the treasury {1} ... was pointedly {2}: subsidies cut ...",
  "blanks": [ { "options": ["languished","abounded","dwindled"], "answers": ["abounded"] },
              { "options": ["equivocal","prodigal","austere"],   "answers": ["austere"] } ],
  "words": ["abound"],
  "explanation": "why the answer fits and why the nearest wrong option does not",
  "gregmat_group": 1,
  "verified": true
}
```

**One shape for all three types**, so the app renders them through one code path.
The only variation is in the blanks:

| type | blanks | options each | answers each | UI |
|---|---|---|---|---|
| `tc2` | 2 | 3 | 1 | two labelled groups, all-or-nothing |
| `se` | 1 | 6 | **2** | one group, "choose two" |
| `cloze` | 1 | 5 | 1 | one group |

`{1}` and `{2}` are the blank placeholders. `normalise_stem()` in `quizgen.py`
rewrites other notations the model sometimes emits — `(i)`, `_____`, `[1]` —
because rejecting those threw away work already paid for.

`rejects` are kept deliberately. They are the evidence that verification is doing
something, and they are useful when tuning prompts.

---

## Client state — `localStorage`

All keys are versioned. **None of this is ever written into generated data.**

| key | contents |
|---|---|
| `gre-vocab-difficulty-v1` | `{ word: "easy"\|"medium"\|"hard" }` — manual marks |
| `gre-vocab-srs-v1` | `{ word: {ef, iv, reps, lapses, due, seen} }` — SM-2 state |
| `gre-vocab-seenq-v1` | array of bank question ids already asked |
| `gre-vocab-route` | last route, so reopening returns you where you were |
| `gre-vocab-qtypes` | enabled quiz types |
| `gre-vocab-qdue` | "only ask what's due" toggle |
| `gre-vocab-gemini-key` | user's own Gemini API key (never leaves the device except to Google) |
| `gre-vocab-gemini-model` | chosen model id |

`due` is a **day number** (`floor(Date.now() / 86400000)`), not a timestamp.

Export/import uses an envelope `{ marks, srs }`. Import still accepts the
original bare-marks object for backward compatibility — keep that.

> `localStorage` is scoped per origin. Marks made on `file://`, on
> `div652.github.io`, and in the Android app are three separate stores. Export/
> import is the only bridge, and this is expected behaviour, not a bug.

---

## Routes

Hash routes, pushed to history so Back works and the last one is persisted.

```
/browse            /browse/<word>
/drill
/quiz              /quiz/<groupId>     group-scoped quiz
/groups            /groups/<groupId>
```

`<groupId>` is a semantic group `id`. A group-scoped quiz draws both its target
words and its distractors from that group, and disables "only what's due"
(a five-word group would otherwise almost always be empty).
