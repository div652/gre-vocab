# Documentation index — start here

You are probably an AI agent who has just been handed this repository. Read this
page fully. It is short, and it will save you from the three mistakes newcomers
make here.

## What this project is

A GRE vocabulary study system for one person. 1,112 words, each explained in a
hand-calibrated card format, grouped seven different ways, and drilled through
2,010 independently verified exam-format questions. It ships as a static web app
(GitHub Pages) and an offline Android APK, both built from the same data.

It is **not** a general-purpose vocabulary tool, and should not be generalised
into one without the owner asking for that.

## The 60-second orientation

```
words.json ──► cards/*.json ──► groups/*/*.json ──► bank/*.json
   (input)       (1 per word)     (7 grouping kinds)   (quiz questions)
                      │                  │                  │
                      └──────────────────┴──────────────────┘
                                         ▼
                         out/flashcards.html  ·  out/groups.md
                         out/group_NN.md      ·  out/anki.tsv
                                         ▼
                          GitHub Pages   ·   Android APK
```

Everything downstream of `cards/` is **regenerable**. `cards/` itself is
regenerable from `skill/SKILL.md`. The single source of truth for *quality* is
that skill file; the single source of truth for *content* is `cards/`.

## Read in this order

| Doc | Read it when |
|---|---|
| **[PHILOSOPHY.md](PHILOSOPHY.md)** | Before changing anything. The invariants live here, and most of them are non-obvious. |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Before touching the pipeline. Explains why generation is a loop and what that buys. |
| **[DATA-MODEL.md](DATA-MODEL.md)** | Before touching any schema, the app, or storage. |
| **[DECISIONS.md](DECISIONS.md)** | Before re-litigating a design choice. Many obvious-looking improvements were already tried and rejected for reasons recorded there. |
| **[OPERATIONS.md](OPERATIONS.md)** | Before running anything that costs money or takes hours. |
| **[MAINTAINING-DOCS.md](MAINTAINING-DOCS.md)** | Before you finish any task. It tells you what to update. |

## The three mistakes newcomers make

**1. Treating the card format as arbitrary.** It was calibrated interactively
over ~15 words, with the owner rejecting things one at a time. A "Memory image"
section was built, refined across several rounds, and then abolished entirely.
Sections are optional *by design*, and `null` is a correct answer. See
PHILOSOPHY § Precision over recall.

**2. Making generation a conversation.** Every card, group and question is
produced by an independent process with a byte-identical frozen prompt. If you
"optimise" this into one long chat to save tokens, quality will drift across the
set and you will not notice, because nobody can eyeball 1,112 cards. See
PHILOSOPHY § Why it is a loop.

**3. Trusting generated content without verification.** Quiz questions are
blind re-solved by a second pass before they ship. 10% get rejected. Removing
that check would be invisible until the owner is marked wrong for a defensible
answer, at which point trust in the whole system is gone.

## Where the owner's preferences live

`skill/SKILL.md` is a vendored copy of a Claude Code skill that encodes exactly
how cards must be written, including rules that exist only because the owner
objected to something. Treat it as a specification, not a suggestion. Read
`skill/reference/exemplar-censor.md` for a card the owner called "perfect".

## Repository layout

```
skill/                 card-format spec (vendored from ~/.claude/skills)
cardspec.py            card JSON schema + deterministic system-prompt assembly
claude_cli.py          shared transport to the Claude Code CLI
extract_words.py       .xlsx -> words.json
generate.py            the card loop
group.py               grouping: mechanical + discover + write + render
quizgen.py             question bank: generate + blind-verify
lint.py                drift detectors for cards (--) and bank (--bank)
render.py              cards -> markdown
build_app.py           cards + groups + bank -> out/flashcards.html
export_anki.py         cards -> Anki TSV
sync_skill.py          keep skill/ in step with the live skill
index.html             Pages landing page (redirects into out/)
android/               WebView shell around out/flashcards.html
.github/workflows/     APK build + release
cards/ groups/ bank/   generated data (committed)
out/                   deliverables (committed)
```
