# Decision log

Every significant choice, what was rejected, and why. Several entries record
things that were **built and then removed** — those are the most valuable, because
they are the ones most likely to be re-proposed.

Format: decision · alternatives rejected · reason.

---

## Card format

### D-01 — The format was calibrated interactively, not designed up front
Fifteen words were explained one at a time, with the owner correcting each. The
result is `skill/SKILL.md`. **Do not redesign it from first principles.** Every
rule in it is a scar.

### D-02 — "Memory image" section: built, refined, then abolished
A vivid one-scene image per word. Iterated across several rounds, then removed
entirely: *"the memory image constantly sucks — remove it entirely, don't give
any memory images in any scenario."*

Failure mode that killed it: images kept dramatising the *etymology* rather than
the word, duplicating the section above them. **Do not reintroduce it under
another name** ("picture this", "scene", "visualise"). The skill file bans it
explicitly.

### D-03 — Sections are optional; `null` is a correct answer
Rejected: always filling every section. That produced padding, which the owner
objected to repeatedly. Precision over recall — one strong hook beats three
adequate ones.

### D-04 — Optional sections are nullable keys, not absent keys
Rejected: omitting keys. Uniform record shape makes rendering, diffing and
loading trivial, and the model needs an explicit place to say "nothing here".

### D-05 — Etymology is a memory aid, not history
Cut: remote or speculative origins that don't illuminate current meaning (the
*phony* ← "fawney rig" con story was true and useless), and foreign-language
cognates. Kept: roots that generalise to other GRE words, and false-friend traps.

### D-06 — "Rule Zero": a title match is always a hook
The original rule required a famous name to share the word's root **and** embody
the meaning. That `and` was too strict — it returned `null` for *acquiesce*
despite Oasis's well-known track, and Oasis is one of the owner's favourite bands.

Fixed by making an exact title match an automatic hook. Regenerating just the
nulls lifted `in_the_wild` coverage from 84.4% to 92.6% — **62 words improved
from one observation.** This is the clearest evidence that the format-in-a-file
architecture pays off.

### D-07 — Banned: any phrase that becomes a formula
"The nuance is everything here" appeared on every card and had to be banned by
name. The general rule is in the skill: if a phrase appeared on the last two
cards, find another way in.

---

## Generation architecture

### D-08 — One independent process per item
Rejected: generating in a long conversation. Context fills, early instructions get
summarised away, and card #900 stops resembling card #12 — invisibly, because
nobody reviews 1,112 cards. See PHILOSOPHY § 2.

### D-09 — The skill file is the single source of quality
Rejected: embedding format rules in Python. The vendored `skill/` copy produces a
byte-identical prompt to the owner's live skill, which is what makes the repo
reproducible rather than merely descriptive.

### D-10 — Prompt on stdin, not argv
Discovered by hitting two separate ceilings: `claude.cmd` routes through
`cmd.exe` (8,191 chars) and even the native binary caps argv at 32,767. stdin has
no such limit — verified at 42,000 characters. This is what allows a
148,000-character index in one discovery call.

### D-11 — Small batches, deliberately
Question generation uses 4 words per call, not 8. A single response producing 16
questions degrades toward the end, for the same reason a long conversation does.
Cost is identical; quality is not.

A related near-miss: an early version passed `len(batch)` as the question count,
so shrinking the batch would silently have **halved output**. The owner caught it.
Questions-per-word is now an explicit `--per-word` flag.

### D-12 — Prompt caching is why this is affordable
The frozen system prompt is the cache prefix. Cold, a card cost $0.27; warm,
~$0.08. `generate.py` runs one warm-up call alone before parallelising. Anything
non-deterministic in `build_system_prompt()` destroys this silently — watch
`cache_read_input_tokens`.

---

## Grouping

### D-13 — Seven grouping schemes
Meaning clusters, root families and lookalikes were requested. Second meanings,
intensity scales, connotation traps and antonym clusters were proposed with
trade-offs and all four accepted.

### D-14 — Confusability is not transitive
Following one-way `confusables` edges collapsed 234 words into one useless
component (*abstain → abstruse → abstract* chains forever). Requiring **mutual**
edges cut 744 directed edges to 192 and produced clean components of 3–7.
**Do not restore the transitive closure.**

### D-15 — Discovery and write-up are separate stages
Discovery sees all 1,112 words at once and returns only membership lists (cheap).
Write-up is one independent call per group. Rejected: one call producing all 655
write-ups, which would degrade badly toward the end.

### D-16 — Nuance must contrast, not re-define
The write-up prompt's test: if a line could be pasted under a different word in
the same group, it is too vague. This is what makes the groups worth reading.

---

## Question bank

### D-17 — Both a pre-generated bank and a live top-up
Rejected: live-only (breaks offline, ~3s latency, unverifiable) and bank-only
(finite). The bank is the default and always works; live is the escape hatch.

### D-18 — Blind re-solve verification
A second call sees the question without the intended answer, must solve it, and
must judge uniqueness. ~10% rejected. Rejected alternatives: no verification
(erodes trust the first time a defensible answer is marked wrong) and
spot-checking a sample.

### D-19 — Generate against GregMat groups, supply distractors from semantic groups
The owner's correction. GregMat groups are the study unit but are arbitrary
batches, so Sentence Equivalence cannot find its co-answer inside one. Target word
from the study group; distractors and co-answer from the semantic clusters.

Side effect: cost fell from a projected ~$530 (655 semantic groups) to ~$200.

### D-20 — Normalise blank notation instead of rejecting it
The model sometimes writes `(i)`/`_____` instead of `{1}`. One pilot batch lost
five of eight questions to this. `normalise_stem()` rewrites them; keep rate went
2/8 → 8/8 on that batch.

### D-21 — Distractor tiers are exhausted in order
Group being quizzed → any group the word belongs to → random. An earlier version
pooled them and shuffled together, letting a random word beat an in-cluster one.
Measured on a five-word group: partial → 25/25 in-group.

---

## Application

### D-22 — One self-contained HTML file
No framework, no build step, no server, no network. Data embedded as JSON at
build time so it works over `file://` and inside a WebView. Rejected: a SPA
framework, a backend, runtime fetching.

### D-23 — Progress lives in `localStorage`, never in the data
Regenerating all 1,112 cards must never touch study progress. Export/import is
the only cross-device bridge.

### D-24 — Hash routing with history
The app was one history entry, so Back left the site entirely. Now every
navigation pushes a route, the last one is persisted, and links to a word or
group are shareable. Also fixes the Android back gesture.

### D-25 — Android: `WebViewAssetLoader` over an https origin
Rejected: `file:///android_asset/`, where `localStorage` is unreliable across
WebView versions — and `localStorage` is the user's progress.

### D-26 — Android export via JS bridge
A `blob:` download inside a WebView is silently dropped by DownloadManager.
Export would have appeared to work and produced nothing.

### D-27 — Stable signing key, held outside the repository
At `~/.gre-vocab-signing/`, injected into CI from repo secrets. A signature change
forces an uninstall, and an uninstall wipes `localStorage`. Rejected: debug
signing (fresh key per CI run) and committing the keystore.

### D-28 — Build the APK in CI, not locally
An Android SDK is a multi-GB local install. CI also guarantees the APK and the web
app cannot drift, since the build triggers on `out/flashcards.html` changing.

### D-29 — Gemini model is discovered, not hardcoded
Settings query the user's key for models supporting `generateContent` and
populate a dropdown. A rename upstream fixes itself.

---

## Infrastructure

### D-30 — Generation runs through the Claude Code CLI, not an API key
The owner cannot create API keys on their account. The CLI authenticates with
their existing login. No script here handles a credential.

### D-31 — Repository is public, with the trade-off named
Originally private, because the word list and its 38-group arrangement are
GregMat's paid product. Made public deliberately so GitHub Pages could serve the
app on the free tier — Pages publishes to a public URL regardless of repo
visibility, so "private repo + Pages" was never actually private.

### D-32 — `out/` is committed
Regenerable, but these are the documents actually read and pasted into Slite, and
`flashcards.html` is what Pages serves.

---

### D-33 — Accounts without a backend: Drive `appDataFolder`
Rejected: Firebase and Supabase. Both give a central queryable database, but both
add a hosted dependency to a project whose defining property is having none, and
both would make the owner custodian of other people's study data. With
`appDataFolder` each user's progress lives in **their own Drive**, so accounts
exist and PHILOSOPHY § 8 survives intact.

The OAuth **web client id is public by design** and is committed. There is no
client secret and there must not be one — a client secret in a static app is
neither secret nor necessary.

### D-34 — Five themes, Aqua default; scale is a CSS variable
Text size is `--scale` multiplying a single `html` font-size, so **all** sizing is
in `rem` and grows together. Rejected: browser zoom (owner asked for an in-app
control) and per-element font sizes (they drift apart).

### D-35 — Prosody by chunking, since the Web Speech API ignores SSML
`<emphasis>` markup does nothing in practice, so stress is produced by *splitting*
instead: the `**bolded**` target word is spoken as its own utterance at rate .68
and pitch 1.22, section boundaries get real pauses by driving the queue manually,
and the voice is chosen by ranking installed voices rather than taking index 0.

The emphasis is **derived from the card data**, not guessed — the bold markers
were already there for the cloze generator. Do not strip them.

Ceiling worth knowing: this is concatenative synthesis and will sound like a good
screen reader, not a person. If natural narration is ever wanted, pre-generating
cloud TTS audio at build time keeps the app offline; calling a TTS API at runtime
does not.

### D-36 — `.hidden` needs `!important`
`.hidden{display:none}` and `.sheet{display:grid}` are both single-class
selectors, so the later one won and the settings sheet was open on every load.
Equal specificity plus source order is a real hazard in a single-file stylesheet.

### D-37 — Quiz scope is a set, and lives in storage rather than the URL
The quiz was scoped to at most one group (`quizGroup`, routed as
`/quiz/<groupId>`). It is now a **set** of scopes, `quizSel`, mixing the 38
GregMat lists and the 655 semantic groups in one picker — 693 tickable scopes,
which is why the picker is searchable and tab-filtered rather than a plain list
of checkboxes.

Three things follow:

- **Deduplication is what shuffles the groups together.** `scopedCards()`
  collects into a `Set` of words before filtering `CARDS`, so a word in three
  selected groups is one pool entry, not three. Without that, overlapping
  selections would silently over-weight whichever words sit in the most groups.
- **The tabs filter the view, not the selection.** "Select all" adds only what
  is currently shown, so it composes with the search box instead of dumping all
  693 in.
- **`/quiz/<groupId>` survives as a shortcut**, not a mode: it sets the scope to
  that one group and `replaceState`s back to `/quiz`. One route for the quiz
  keeps the back button honest.

### D-38 — Distractors ignore the quiz scope
Wrong options are drawn from the word's own semantic groups first, then from
anywhere in the deck — deliberately **independent of what is selected**.

Selecting groups narrows which words get *asked*, not what they compete against.
The earlier behaviour drew distractors from the scope, which meant that
quizzing a GregMat list — an arbitrary 30 words with no semantic relation —
filled every question with unrelated options and made it trivially easy.

Keep the tiering. Shuffling near-synonyms together with random words would let
a random word beat an in-cluster one, which is exactly what makes a question
easy.

### D-39 — Video links live outside the cards
`videos.json` is keyed by word and loaded alongside `groups/` and `bank/`, rather
than adding a field to each card. Cards are model-authored under a frozen prompt;
scraped data in them would blur what the generation loop is accountable for. The
practical payoff is that re-crawling the channel touches one file.

### D-40 — Exact-form matching, and literature videos excluded
Two filters carry the precision, and both were added after seeing real failures:

- **Exact surface form only.** Morphological matching gained 20 words and lost
  about half of them to nonsense: *commence* → a video on Spanish elections (via
  "Comment"), *universal* → "University", *passable* → "Pass".
- **No literature videos.** The channel also does poetry analysis. Raising the
  subject cap to admit the big synonym round-ups ("Moan Groan Bellyache Grumble
  Grouse…", genuinely the best group videos) also admitted "Bright Star Would I
  Were Steadfast Thou Art - John Keats - Analysis", where every proper noun
  parses as a subject.

A third failure is worth remembering because it was self-inflicted: the category
stoplist that strips "Essential Adjectives" from a title also contained
*sophisticated*, which is a card word. Any stoplist here must be diffed against
the word list.

---

## Corrections worth remembering

Three times a *detector* was wrong rather than the data:

1. Lint flagged `forgo` and `stem from` — the cards were right (irregular past
   "forwent"; phrasal "stemmed from"). The linter was fixed, not the cards.
2. The bank leak detector flagged `assuage`/"assumed" and `largesse`/"larger" —
   pure prefix matching. Tightened to require an inflection.
3. The tightened version then **missed** `vilify`/"vilified" (y→i) and
   `abet`/"abetted" (consonant doubling). Only a two-directional test caught it.

**Always look at the flagged item before changing the data.**
