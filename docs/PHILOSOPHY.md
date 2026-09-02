# Philosophy and invariants

The rules here are not style preferences. Each exists because something failed
without it, and most were paid for in money or in the owner's time. Breaking one
will usually not produce an error — it will produce quietly worse output that
nobody notices for a thousand items.

---

## 1. Quality is a specification, not a vibe

`skill/SKILL.md` defines what a good card is. It is the *only* place that
definition lives. `cardspec.py` reads it off disk and assembles it into a frozen
system prompt, so changing the skill changes every future card and nothing else
has to be touched.

**Invariant:** never duplicate card-format rules into a prompt string, a Python
constant, or your own head. If a rule needs to change, change the skill, run
`sync_skill.py`, and regenerate.

The vendored copy under `skill/` must stay byte-identical to the owner's live
skill at `~/.claude/skills/gre-word-coach/`. This was verified — the same
13,007-character prompt is produced from either source. That equality is what
makes the repository genuinely reproducible rather than merely documented.

---

## 2. Why it is a loop, not a conversation

Quality degrades in long conversations. Context fills, early instructions get
summarised away, and item #900 stops resembling item #12. Nobody can eyeball
1,112 cards, so the degradation would ship.

So **nothing is shared between items.** Each card, each group write-up, each
batch of questions is a separate process, with a byte-identical frozen system
prompt, that writes one file and exits.

Four properties follow, and all four are load-bearing:

- **No drift.** Word #1 and word #1,112 are produced under identical conditions.
- **Resumable.** One file per item; existing files are skipped. When the question
  bank was throttled and took 17 hours instead of 1, that cost time and nothing
  else.
- **Individually repairable.** A bad item is one `--force --only <x>` away from
  being fixed, without touching the rest.
- **Mechanically checkable.** `lint.py` asserts the format rules in code, because
  human review does not scale to this volume.

**Invariant:** do not consolidate generation into fewer, longer calls to save
tokens. The batch size in `quizgen.py` is deliberately small (4 words per call)
for exactly this reason — see DECISIONS § D-11.

---

## 3. Precision over recall

The card format's hardest-won rule. **Content that is merely true, interesting,
or complete is bloat and must be cut.**

Only three card sections are mandatory: the heading line, `Means`, and
`In sentences`. Everything else — etymology, the mnemonic, the pop-culture hook,
the false-friend trap — is optional and omitted when it is not strong.

The model is told explicitly, in the output contract, that **`null` is a correct
answer, not a failure.** Without that sentence it pads, and padding is the single
thing the format was tuned hardest against.

Corollaries that came from specific owner corrections:

- Never write a section that explains its own absence ("this word has no famous
  usage"). Omit it silently.
- Never invent a lyric, quotation, or reference. 82 words legitimately carry
  `in_the_wild: null`.
- Never let a phrase become a formula across items. The stock opener "The nuance
  is everything here" was used on every card and had to be banned outright.

---

## 4. Optional means optional — structurally

Optional sections are **required keys with nullable values**, not absent keys.
Every record therefore has an identical shape, which makes rendering, diffing and
loading trivial, while still letting a word carry `null`.

**Invariant:** do not "clean up" the schema by removing keys whose value is null.
Downstream code assumes uniform shape.

---

## 5. Generated content is not trusted until verified

Two independent checks exist, and they do different jobs.

**`lint.py` — mechanical.** Asserts the format contract: exactly two sentences,
each genuinely using the word; `trick_unpack` exactly one sentence; both trick
halves or neither; no banned phrasing; pronunciation carries capitalised stress.

**Blind re-solve — semantic.** Every quiz question is solved by a *second*
independent call that is not told the intended answer and must also judge whether
exactly one answer is defensible. Only agreement on both keeps the question.
About 10% are rejected.

This catches the failure that matters: a question where two options both
genuinely fit, so a reasonable answer is marked wrong. One such rejection read:

> "Nothing in the sentence forces the referent one way, so a reasonable
> test-taker who picks 'credible' has a genuine defense and would be marked
> wrong."

**Invariant:** never ship generated questions without the blind re-solve. It
roughly doubles cost and that is the correct trade. If you add a new question
type, it must go through the same gate.

The one deliberate exception is the optional Gemini live top-up, which cannot be
verified before display. It is therefore **off by default and labelled unverified
in the UI.** Do not remove that label.

---

## 6. The user's progress is sacred

Difficulty marks and spaced-repetition state live in browser `localStorage`,
**never in the generated data.** Regenerating all 1,112 cards must never touch
study progress.

This is also why the Android app is signed with a stable key held outside the
repository: a signature change would force an uninstall, and an uninstall wipes
`localStorage`.

**Invariant:** any new per-user state goes in `localStorage` under a versioned
key, and must be included in export/import.

---

## 7. Verify claims before acting on them

A recurring pattern in this project's history: a check reported a problem, and
the check was wrong.

- The bank leak detector flagged `assuage` against "assumed" and `largesse`
  against "larger". Both false. Tightened.
- The tightened version then *missed* `vilify` against "vilified" and `abet`
  against "abetted". Caught only because a test covered both directions.
- Three of five early lint failures were the linter's fault, not the cards'
  (irregular inflections, phrasal verbs).

**Invariant:** when a detector fires, look at the actual item before "fixing" the
data. A detector that silently under-reports is worse than none, so tests must
cover both false positives and misses.

---

## 8. Scope discipline

This is a personal study aid for one person preparing for one exam. Resist:

- generalising it into a multi-user product
- adding a backend (the entire system is static files by design)
- adding dependencies (the app is one self-contained HTML file with no
  framework, no build step, and no network requirement)

The owner asks for things directly. Build what was asked, show examples before
building, and ask about design choices rather than deciding them alone.
