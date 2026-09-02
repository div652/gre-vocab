# Maintaining these documents

This file exists so the repository stays handover-ready **permanently**, not just
on the day the docs were written. If you are an agent working on this project,
this is part of your task, not an optional courtesy.

## The contract

> **A change is not finished until the documentation that describes it is
> correct.** Code and docs land in the same commit.

The reason is specific to how this project is used: the owner hands the whole
repository to a fresh AI agent with no conversation history. Everything that
agent needs must be *in the repository*. A decision whose rationale exists only
in a chat log is a decision that will be silently reversed later.

---

## What to update, by what you changed

| If you changed… | Update |
|---|---|
| `skill/SKILL.md` — card format rules | PHILOSOPHY (if an invariant moved), DECISIONS (new entry — say what was rejected), and run `python sync_skill.py` |
| Any JSON schema | **DATA-MODEL** — it is authoritative and must match the code |
| A pipeline stage, or added one | ARCHITECTURE diagram + stage section, OPERATIONS commands |
| A prompt's rules | DECISIONS (why), and PHILOSOPHY if it encodes a new invariant |
| `localStorage`, routes, app state | DATA-MODEL § Client state / Routes |
| Quiz types or distractor logic | ARCHITECTURE § Question types, DECISIONS |
| CI, signing, deployment | OPERATIONS § Deployment |
| Counts (cards, groups, questions) | run `python docs_check.py` and fix what it flags |
| Anything that cost money | OPERATIONS § Costs, with the **measured** figure |
| Something you tried that did not work | **DECISIONS** — this is the highest-value entry type |

---

## Record failures, not just successes

The most useful entries in DECISIONS are things that were built and removed, or
fixed twice because the first fix was wrong. They are what stop the next agent
from cheerfully reintroducing a known bad idea.

When you record one, include:

1. what was tried
2. what actually went wrong — concretely, with the specific case
3. what replaced it
4. whether it is banned outright or merely not preferred

Good example to imitate — DECISIONS § D-02, the abolished memory-image section:
it names the failure mode (images dramatised the etymology rather than the word),
quotes the owner's verdict, and explicitly bans reintroduction under another name.

---

## End-of-task checklist

Run before you consider any substantive change complete:

```bash
python lint.py                 # cards clean?
python lint.py --bank          # bank clean?
python sync_skill.py --check   # vendored skill in step with the live one?
python docs_check.py           # do the docs still state true things?
```

Then ask yourself the two questions the checks cannot:

- **Would a fresh agent reading only `docs/` make the same choice I made?** If
  not, the rationale is missing — write it down.
- **Did I contradict an existing invariant?** If deliberately, update PHILOSOPHY
  and say why in DECISIONS. If accidentally, undo it.

---

## `docs_check.py`

Verifies the factual claims in the docs against the repository — counts of cards,
groups, bank questions, grouping kinds, schema fields, `localStorage` keys and
routes. It is a **drift detector for prose**, in the same spirit as `lint.py`
being a drift detector for generated content.

Two blind spots, stated so you do not over-trust it:

- It cannot check whether the *reasoning* is still true. That part is yours.
- Presence checks are substring matches over the whole file, so it catches
  something **new** going undocumented, but not something being moved out of the
  right table while the word survives elsewhere. Verified by negative test.

---

## Style

These documents are read by agents under context pressure. Optimise for that:

- **Lead with the invariant, then the reason.** "Do not X, because Y" beats three
  paragraphs of background.
- **Name the concrete failure.** "234 words collapsed into one component" is
  actionable; "the clustering was poor" is not.
- **Keep tables for facts, prose for reasoning.**
- **Do not duplicate.** Cross-reference instead — duplicated facts drift apart.
- Same rule the cards follow: **precision over recall.** Content that is merely
  true is bloat. If a section would not change an agent's behaviour, cut it.

---

## When the project changes shape

If a change is large enough that the ARCHITECTURE diagram is wrong — a new
pipeline stage, a second output target, a different model — do not patch around
it. Rewrite the affected section, add a DECISIONS entry explaining the shift, and
update the orientation in `docs/README.md`.

The test is always the same: **could someone with no history here take over
tomorrow using only this repository?**
