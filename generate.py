"""
Generate one GRE vocabulary card per word, via the Claude Code CLI.

Each word is an INDEPENDENT process with an identical frozen system prompt, so
word #1 and word #1112 are produced under the same conditions. This is a real
for-loop, not a long conversation - there is no shared context to drift.

Resumable: one file per word in cards/. Words whose file exists are skipped, so
an interrupt costs nothing. Failures are left unwritten and retried next run.

    python generate.py --limit 30          # pilot
    python generate.py                     # everything remaining
    python generate.py --only accord phony --force

Auth comes from `claude auth login` (already done). No credentials are handled
by this script.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import claude_cli
from cardspec import CARD_SCHEMA, build_system_prompt, slug

HERE = Path(__file__).parent
CARDS = HERE / "cards"
WORDS = HERE / "words.json"
FAILURES = HERE / "failures.log"

_lock = threading.Lock()


def log(msg: str) -> None:
    with _lock:
        print(msg, flush=True)


def generate_one(system: str, word: str) -> tuple[dict, dict]:
    """Return (card, usage). Raises on unrecoverable failure."""
    card, usage = claude_cli.call(system, f"Word: {word}", CARD_SCHEMA)
    if "word" not in card:
        raise claude_cli.CliError("result has no 'word' field")
    return card, usage


def card_path(word: str) -> Path:
    return CARDS / f"{slug(word)}.json"


def save(word: str, groups: list[int], card: dict) -> None:
    card = {**card, "word": card.get("word") or word, "groups": groups}
    p = card_path(word)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", type=Path, default=WORDS)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", nargs="+")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--null-field", metavar="FIELD",
                    help="regenerate only cards whose FIELD is null/empty "
                         "(e.g. --null-field in_the_wild after a skill fix). Implies --force.")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    if not claude_cli.EXE.exists():
        log(f"claude.exe not found at {claude_cli.EXE}")
        return 2

    CARDS.mkdir(exist_ok=True)
    records = json.loads(args.words.read_text(encoding="utf-8"))

    if args.only:
        want = {w.lower() for w in args.only}
        records = [r for r in records if r["word"].lower() in want]

    if args.null_field:
        keep = []
        for r in records:
            p = card_path(r["word"])
            if not p.exists():
                keep.append(r)
                continue
            try:
                if not json.loads(p.read_text(encoding="utf-8")).get(args.null_field):
                    keep.append(r)
            except Exception:  # noqa: BLE001 - unreadable card is worth redoing
                keep.append(r)
        records = keep
        args.force = True

    pending = records if args.force else [r for r in records if not card_path(r["word"]).exists()]
    todo = pending[:args.limit] if args.limit else pending

    log(f"{len(records)} selected | {len(records) - len(pending)} already on disk | "
        f"{len(pending)} pending | {len(todo)} this run")
    if not todo:
        return 0

    system = build_system_prompt()
    log(f"system prompt {len(system):,} chars\n")

    totals = {"cost": 0.0, "out": 0, "cache_r": 0, "cache_w": 0}
    done = failed = 0
    total = len(todo)
    started = time.time()

    def work(rec: dict):
        card, usage = generate_one(system, rec["word"])
        save(rec["word"], rec["groups"], card)
        return rec["word"], usage

    # One call first, alone, to warm the server-side prompt cache. Firing six
    # cold calls at once would make all six pay full price for the prefix.
    warm, rest = todo[:1], todo[1:]
    for phase, batch, workers in (("warm", warm, 1), ("main", rest, args.workers)):
        if not batch:
            continue
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(work, r): r for r in batch}
            for fut in as_completed(futs):
                rec = futs[fut]
                try:
                    word, u = fut.result()
                    done += 1
                    totals["cost"] += u.get("cost", 0) or 0
                    totals["out"] += u.get("output_tokens", 0) or 0
                    totals["cache_r"] += u.get("cache_read_input_tokens", 0) or 0
                    totals["cache_w"] += u.get("cache_creation_input_tokens", 0) or 0
                    n = done + failed
                    rate = n / max(time.time() - started, 1e-9)
                    log(f"  [{n:>4}/{total}] {word:<22} ok    "
                        f"${totals['cost']:6.2f}  eta {(total - n) / rate / 60:5.1f}m")
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    with _lock:
                        FAILURES.open("a", encoding="utf-8").write(f"{rec['word']}\t{e}\n")
                    log(f"  [{done + failed:>4}/{total}] {rec['word']:<22} FAIL  {e}")

    mins = (time.time() - started) / 60
    log(f"\ndone {done}, failed {failed}, {mins:.1f} min, ${totals['cost']:.2f}")
    log(f"output tokens {totals['out']:,} | cache read {totals['cache_r']:,} "
        f"| cache write {totals['cache_w']:,}")
    if done:
        log(f"per card: ${totals['cost'] / done:.4f}, {mins * 60 / done:.0f}s")
    if failed:
        log(f"failures in {FAILURES} - re-run to retry (finished words are skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
