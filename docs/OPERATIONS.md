# Operations

Read this before running anything that costs money or takes hours.

---

## Environment

| Requirement | Notes |
|---|---|
| Python 3.12+ | `pip install openpyxl` (only for `extract_words.py`) |
| Claude Code CLI | `npm i -g @anthropic-ai/claude-code`, then `claude auth login` |
| Node 18+ | only to install the CLI |
| `gh` CLI | only for repo/release operations |
| Android SDK | **not needed** — the APK builds in CI |

Everything else is stdlib. There is no `requirements.txt` because there are
effectively no dependencies.

### Windows gotchas that cost real debugging time

**Invoke `bin/claude.exe`, never `claude.cmd`.** The shim goes through `cmd.exe`,
which caps the command line at 8,191 characters; the system prompt alone is
~13,000. `claude_cli.EXE` already points at the binary.

**Set `PYTHONIOENCODING=utf-8`** on every run, or printing card text dies on
cp1252 with `UnicodeEncodeError`.

**PowerShell execution policy blocks `.ps1` shims.** Use `claude.cmd` / `gh.exe`
by full path in an interactive shell.

**A newly-updated PATH is not visible to already-open shells.** Windows only
hands the new environment to newly-created processes.

**Heredocs that write Python containing `\n` escapes can collapse them into real
newlines.** This produced unterminated string literals twice. Prefer the `Edit`
tool for code changes, or build the escape as `chr(92) + "n"`.

---

## Running the pipeline

```bash
# 1. word list (only if the source spreadsheet changes)
python extract_words.py                      # auto-finds *Vocab List*.xlsx in Downloads

# 2. cards  -- ALWAYS pilot first
python generate.py --limit 30
python lint.py                               # must be clean before scaling
python generate.py --workers 8

# 3. groups
python group.py mechanical                   # free, no model
python group.py discover
python group.py write --workers 8
python group.py render

# 4. question bank
python quizgen.py --groups 1 --print         # pilot one GregMat group
python lint.py --bank
python quizgen.py --per-batch 4 --per-word 2 --workers 6

# 5. deliverables
python render.py && python build_app.py && python export_anki.py
git add -A && git commit && git push         # Pages + APK rebuild automatically
```

### Targeted regeneration

```bash
python generate.py --force --only querulous phony
python generate.py --null-field in_the_wild          # after a skill fix
python generate.py --force --only $(python lint.py --fixlist)
python quizgen.py --groups 7 --force
```

Everything is resumable: existing output files are skipped unless `--force`.

---

## Costs — measured, not estimated

| Run | Volume | Cost |
|---|---|---|
| Cards | 1,112 | **$103.74** (+ ~$31 in pilots, fixes and refills) |
| Group discovery | 5 calls over all words | $6.15 |
| Group write-ups | 655 | **$61.90** |
| Question bank | 2,010 kept of 2,230 | **$202.52** |
| **Total** | | **≈ $395** |

Per-unit: **~$0.096 per card**, ~$0.095 per group write-up, **~$0.101 per usable
question** (which includes paying for the ~10% that verification rejects).

Two things to know before quoting these:

- The figures come from the CLI's `total_cost_usd`. The owner's login is on a
  Microsoft enterprise plan, so this may be a **notional API-equivalent** figure
  rather than anything billed.
- Cost is dominated by **output** tokens. Prompt caching already removes most of
  the input cost — check `cache_read_input_tokens` is non-zero.

---

## Throttling — expect it

The question bank was projected at ~1 hour from its pilot. **It took 17.2 hours**,
in bursts, with one three-hour window producing two batches. That is what usage
limits look like, not a hang.

How to tell a stall from a throttle:

```bash
# batches completed per hour, from file mtimes
python -c "
import glob,os,time
ts=sorted(os.path.getmtime(f) for f in glob.glob('bank/*.json')); now=time.time()
for w,l in ((900,'15 min'),(3600,'1 h'),(10800,'3 h')):
    print(l, sum(1 for t in ts if now-t<w))"
```

If fresh `claude.exe` processes are spawning, it is alive. Resumability means
throttling costs time and nothing else — leave it running and ship what exists.

Also worth periodically checking for **orphaned `claude.exe` processes** from
earlier sessions; eleven 61-hour-old ones were found holding memory.

---

## Verification gates

Never skip these.

```bash
python lint.py            # cards: format contract. Must be 1112/1112 clean.
python lint.py --bank     # questions: structure, options, answer leaks.
python sync_skill.py --check   # is skill/ in step with the live skill?
```

Before committing after any format change, `python sync_skill.py` to refresh the
vendored copy, or the repo stops reproducing its own output.

---

## Deployment

Both targets are automatic on push to `main`.

**Pages** serves `index.html` (a redirect) and `out/`. Confirm with:
```bash
gh api repos/div652/gre-vocab/pages/builds/latest --jq .status   # -> "built"
curl -sI https://div652.github.io/gre-vocab/out/flashcards.html | head -1
```

**APK** builds only when `out/flashcards.html` or `android/` changes, so the two
cannot drift. Each run publishes a release, making
`/releases/latest/download/gre-vocab.apk` a stable URL.

Required repo secrets (already set):
`ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`,
`ANDROID_KEY_PASSWORD`.

**The signing keystore lives at `~/.gre-vocab-signing/`, outside the repository.**
Losing it means future APKs cannot install over existing ones without an
uninstall, which wipes the user's study progress. Back it up.

---

## Failure modes seen in practice

| Symptom | Cause | Fix |
|---|---|---|
| `ENOTFOUND` on many words at once | transient DNS | re-run; saves only happen on success, so nothing is lost |
| `checkReleaseDuplicateClasses` | androidx pulls `kotlin-stdlib` twice | legacy `kotlin-stdlib-jdk7/8` are excluded in `app/build.gradle.kts` |
| "The command line is too long" | `claude.cmd` via `cmd.exe` | use `bin/claude.exe` |
| `cache_read_input_tokens` is 0 | prompt prefix not byte-stable | check `build_system_prompt()` for anything varying |
| Cards fail lint after a linter change | usually the linter | inspect the card before touching data (DECISIONS § Corrections) |
