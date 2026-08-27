"""
Mechanically check every generated card against the format contract.

This is the drift detector. With ~1100 stateless calls nobody can eyeball the
output, so the rules the user actually cares about are asserted in code here.
Run it after every generation pass.

    python lint.py            # summary + first 40 problems
    python lint.py --all      # every problem
    python lint.py --fixlist  # bare word list, feed to: generate.py --force --only ...
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from cardspec import CARD_SCHEMA

CARDS = Path(__file__).parent / "cards"

REQUIRED = CARD_SCHEMA["required"]
NULLABLE = {k for k, v in CARD_SCHEMA["properties"].items()
            if isinstance(v.get("type"), list) and "null" in v["type"]}
ARRAYS = {k for k, v in CARD_SCHEMA["properties"].items() if v.get("type") == "array"}

# Phrases the user explicitly banned, plus the abolished section under any alias.
BANNED = [
    r"the nuance is everything",
    r"^#{1,4}\s*memory image",
    r"\bpicture this\b",
    r"\bvisuali[sz]e this\b",
]

ENUMS = {k: set(v["enum"]) for k, v in CARD_SCHEMA["properties"].items() if "enum" in v}


def stem(word: str) -> str:
    """Crude morphological stem so 'vilify' matches 'vilified'."""
    w = word.strip().lower()
    if " " in w:
        return w
    return w[:max(4, len(w) - 3)]


def check(card: dict, path: Path) -> list[str]:
    p: list[str] = []
    word = card.get("word", path.stem)

    for k in REQUIRED:
        if k not in card:
            p.append(f"missing key '{k}'")
    for k in REQUIRED:
        if k in card and card[k] is None and k not in NULLABLE and k not in ARRAYS:
            p.append(f"'{k}' is null but is not nullable")

    for k, allowed in ENUMS.items():
        if card.get(k) not in allowed:
            p.append(f"'{k}'={card.get(k)!r} not in {sorted(allowed)}")

    # --- sentences: exactly two, and each must actually use the word ---------
    sents = card.get("sentences") or []
    if len(sents) != 2:
        p.append(f"{len(sents)} sentences (must be exactly 2)")
    s = stem(word)
    for i, sent in enumerate(sents, 1):
        if s not in (sent or "").lower():
            p.append(f"sentence {i} never uses '{word}'")

    # --- trick: both halves or neither, and the unpack is ONE sentence -------
    line, unpack = card.get("trick_line"), card.get("trick_unpack")
    if bool(line) != bool(unpack):
        p.append("trick_line and trick_unpack must both be present or both null")
    if unpack:
        # Count sentence-final punctuation not inside an abbreviation.
        n = len([x for x in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'“])", unpack.strip()) if x])
        if n > 1:
            p.append(f"trick_unpack is {n} sentences (must be exactly 1)")

    # --- pronunciation must carry stress via capitals ------------------------
    pron = card.get("pron") or ""
    if not pron:
        p.append("empty pron")
    elif not re.search(r"[A-Z]{2,}", pron):
        p.append(f"pron {pron!r} has no CAPITALISED stressed syllable")

    # --- one_line budget ----------------------------------------------------
    ol = (card.get("one_line") or "").split()
    if not ol:
        p.append("empty one_line")
    elif len(ol) > 12:
        p.append(f"one_line is {len(ol)} words (max 12)")

    if not (card.get("means") or "").strip():
        p.append("empty means")

    # --- banned phrasing anywhere in the prose ------------------------------
    prose = "\n".join(str(card.get(k) or "") for k in
                      ("means", "trap", "trick_line", "trick_unpack", "in_the_wild", "etymology"))
    for pat in BANNED:
        if re.search(pat, prose, re.I | re.M):
            p.append(f"banned phrasing matched /{pat}/")

    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--fixlist", action="store_true")
    args = ap.parse_args()

    files = sorted(CARDS.glob("*.json"))
    if not files:
        print(f"no cards in {CARDS}")
        return 1

    bad: dict[str, list[str]] = {}
    kinds: Counter[str] = Counter()
    optional_filled = Counter()

    for f in files:
        try:
            card = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            bad[f.stem] = [f"unparseable: {e}"]
            kinds["unparseable"] += 1
            continue
        for k in ("trick_line", "in_the_wild", "etymology", "trap"):
            if card.get(k):
                optional_filled[k] += 1
        probs = check(card, f)
        if probs:
            bad[card.get("word", f.stem)] = probs
            for pr in probs:
                kinds[re.sub(r"'[^']*'|\d+", "*", pr)[:60]] += 1

    if args.fixlist:
        print(" ".join(sorted(bad)))
        return 0

    n = len(files)
    print(f"{n} cards, {n - len(bad)} clean, {len(bad)} with problems\n")

    print("optional sections present:")
    for k in ("trick_line", "in_the_wild", "etymology", "trap"):
        c = optional_filled[k]
        print(f"  {k:<14} {c:>5} / {n}  ({c / n:5.1%})")

    if kinds:
        print("\nproblem types:")
        for kind, c in kinds.most_common():
            print(f"  {c:>4}  {kind}")

    if bad:
        print("\ndetail:")
        for i, (w, probs) in enumerate(sorted(bad.items())):
            if not args.all and i >= 40:
                print(f"  ... and {len(bad) - 40} more (--all to see them)")
                break
            print(f"  {w}")
            for pr in probs:
                print(f"      - {pr}")
        print("\nregenerate them with:")
        print("  python generate.py --force --only $(python lint.py --fixlist)")

    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
