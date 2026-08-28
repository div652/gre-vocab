# GRE Vocab

1112 GRE words, each explained in a fixed, hand-calibrated card format, generated
once into JSON and rendered into study documents and an offline flashcard app.

## The idea

The card format was tuned interactively over a couple of dozen words until it was
right — what belongs in a card, what counts as bloat, when a section should be
dropped entirely rather than padded. That format lives in a Claude Code skill
(`skill/SKILL.md`), and it is the single source of truth for every card.

The hard part isn't writing one good card. It's writing the **thousandth** one to
the same standard.

## Why it's a loop, not a conversation

Quality degrades in long conversations: context fills, earlier instructions get
summarised away, and card #900 stops resembling card #12. So nothing is shared
between words.

Each word is a **separate process** with a byte-identical frozen system prompt,
constrained by a JSON schema, writing one file and exiting. Word #1 and word #1112
are produced under the same conditions. There is no shared state to drift.

Three consequences worth naming:

- **Resumable.** One file per word. Interrupt it, re-run it, and it picks up where
  it stopped. Nothing is recomputed.
- **Individually repairable.** A bad card is one `--force --only <word>` away from
  being fixed, without touching the other 1111.
- **Mechanically checkable.** With 1112 stateless calls nobody can eyeball the
  output, so `lint.py` asserts the format rules in code.

## Layout

| File | Role |
|---|---|
| `skill/` | The card format spec. Vendored copy of the live Claude Code skill — the thing that actually defines quality. |
| `cardspec.py` | Card JSON schema + deterministic system-prompt assembly. One definition, shared by generator and linter. |
| `extract_words.py` | `.xlsx` → `words.json` (1112 words, groups 1–38). |
| `generate.py` | The loop. Parallel, resumable, retrying. |
| `lint.py` | Drift detector. Run after every generation pass. |
| `render.py` | `cards/*.json` → markdown, one file per group. |
| `build_app.py` | `cards/*.json` → `out/flashcards.html`, a self-contained offline app. |
| `sync_skill.py` | Keeps `skill/` in step with the live skill. |
| `cards/` | One JSON file per word. The source of truth. |

## The schema

Optional card sections are **required keys with nullable values**. Every record
therefore has an identical shape — trivial to render, diff, and load — while a word
with no honest pop-culture hook simply carries `null` there.

This matters more than it looks. The model is told explicitly that `null` is a
correct answer, not a failure. Without that, it pads, and padding was the single
thing the format was tuned hardest against.

Alongside the prose fields, each card carries machine-readable ones — `root`,
`root_family`, `confusables`, `sense_tags`, `register`, `connotation` — which exist
to drive the cross-word grouping analysis and the app's search.

## Running it

```bash
pip install openpyxl
python extract_words.py                 # xlsx -> words.json
python generate.py --limit 30           # pilot first, always
python lint.py                          # verify before scaling
python generate.py --workers 8          # the rest
python render.py                        # -> out/group_NN.md
python build_app.py                     # -> out/flashcards.html
```

Generation shells out to the Claude Code CLI, authenticated with
`claude auth login`. **No API keys are handled by any script here.**

Two Windows details that cost some debugging:

- Invoke `bin/claude.exe` directly, **not** `claude.cmd`. The `.cmd` shim routes
  through `cmd.exe`, which caps the command line at 8191 characters — the system
  prompt alone is ~13,000. The native binary gets the 32,767 `CreateProcess` limit.
- Set `PYTHONIOENCODING=utf-8`, or printing card text dies on cp1252.

## The flashcard app

`out/flashcards.html` is one file — no server, no network, no build step. Open it
by double-clicking.

**Browse** lists every word with a one-line gloss, searchable across meaning, root
and sense tags. **Drill** shows word and pronunciation, reveals the full card on
`space`, and takes a difficulty mark on `1` / `2` / `3`.

Difficulty marks are stored in browser `localStorage`, never in the cards, with
export/import to `difficulty.json`. Regenerating all 1112 cards will not touch your
progress.

## Live

**https://div652.github.io/gre-vocab/** — the flashcard app, served by GitHub Pages.
It is one self-contained file with no server or network dependency, so it works
offline once loaded and runs the same on a phone as on a desktop.

## Source data

The word list and its 38-group arrangement come from GregMat's vocabulary list, a
paid product; the source `.xlsx` is gitignored. This is a personal study aid, and
the card and group content is generated rather than reproduced. If you are from
GregMat and would rather this were not public, open an issue and I will take it
down.
