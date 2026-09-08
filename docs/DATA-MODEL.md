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
| `gre-vocab-qscope-v1` | array of selected quiz scope ids — see below |
| `gre-vocab-gemini-key` | user's own Gemini API key (never leaves the device except to Google) |
| `gre-vocab-gemini-model` | chosen model id |
| `gre-vocab-prefs-v1` | `{theme, scale, voice, rate}` — appearance and reading voice |

### `videos.json`

Word → up to two iswearenglish videos, built by `videos.py` and kept **out** of
the card files: the cards are what the model wrote under the frozen prompt, and
mixing scraped data into them muddies that. It also means re-crawling the
channel rewrites one file instead of all 1112.

```json
{
  "beguile": [
    {"id": "VQeUPWZLx1U", "kind": "dedicated", "subjects": ["Beguile"]},
    {"id": "AbgbD958s5o", "kind": "group",
     "subjects": ["Cajole", "Wheedle", "Entice", "Induce", "Beguile"]}
  ]
}
```

`videos/catalogue.json` is the raw crawl (19,786 id → title pairs), committed so
the match is reproducible without re-crawling. 1015 of 1112 words match; the
other 97 render a channel-search link instead.

Links appear inside **Means**, between the one-line definition and the nuance
paragraph — so `build_app.py` splits `means` on its first blank line rather than
rendering it whole. They render as two 16:9 thumbnails from
`i.ytimg.com/vi/<id>/mqdefault.jpg`, fetched lazily rather than bundled (D-43);
a word with no match gets a channel-search chip instead.

### Quiz scopes

Two unrelated taxonomies are quizzable and the picker mixes them freely, so
`build_app.py` normalises both into one shape at load:

```js
{ id, kind, title, words: [{word}] }
```

- **GregMat lists** are derived in the browser from each card's `groups: [n]`
  field. Their ids are `list:<n>` (`list:12`), prefixed so they can never
  collide with a group slug. 38 of them, ~30 words each.
- **Semantic groups** are the `groups/` files, used as-is. 655 of them.

`gre-vocab-qscope-v1` holds ids from either taxonomy in one flat array. Ids that
no longer resolve are dropped on load, so a stale selection from an older build
degrades quietly instead of producing an empty quiz.

The selection is **not** in the URL. `/quiz/<groupId>` still works as a shortcut
— it sets the scope to that one group and rewrites itself to `/quiz` — but
twenty group slugs in a hash would be unreadable, and the selection has to
survive a reload regardless.

### Signed-in storage — Google Drive

When signed in, the same three progress keys are mirrored to a single file,
`gre-vocab-progress.json`, in the Drive **`appDataFolder`** — a hidden per-user
folder the app can only see its own files in, never the user's real Drive.

```json
{ "marks": {...}, "srs": {...}, "seenq": [...], "updatedAt": 1756..., "v": 1 }
```

Merge is **per key, not last-writer-wins on the blob**: marks are unioned with
local winning ties, and each word's SRS record is taken from whichever side has
the higher `seen` count. Two devices used on the same day would otherwise
silently discard one of them. Pushes are debounced 4s after a progress change.

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
/quiz              /quiz/<groupId>     shortcut: scope to one group, then
/groups            /groups/<groupId>   rewrites itself to /quiz
```

The quiz has one route. `/quiz/<groupId>` — what the "quiz just these words"
button on a group emits — sets the scope to that single group, `replaceState`s
back to `/quiz`, and is gone from history; the scope itself lives in
`gre-vocab-qscope-v1`.

"Only ask what's due" applies inside a selection, but **falls back to the whole
selection when nothing in it is due**, so a five-word group never dead-ends on
an empty screen.
