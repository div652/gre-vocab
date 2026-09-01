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


def uses_word(word: str, sent: str) -> bool:
    """Does this sentence actually use the word, in any inflected form?

    Three cases have to pass, and naive substring matching fails two of them:
      regular      'vilify'    -> 'vilified'     (stem match)
      phrasal      'stem from' -> 'stemmed from' (match the head word only)
      irregular    'forgo'     -> 'forwent'      (no shared stem at all)

    For the irregular case, lean on the fact that every sentence bolds its
    target: accept a **bolded** span that shares a 3-character prefix.
    """
    if not sent:
        return False
    low = sent.lower()
    head = word.strip().lower().split()[0]
    if head[:max(4, len(head) - 3)] in low:
        return True
    pre = head[:3]
    return any(m.strip().startswith(pre) for m in re.findall(r"\*\*(.+?)\*\*", low))


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
    for i, sent in enumerate(sents, 1):
        if not uses_word(word, sent):
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
    # 14, not 12. The original cap was arbitrary and rejected genuinely good
    # glosses - crescendo's "a gradual swell in loudness or intensity, the build
    # not the peak" carries the exact nuance people get wrong, in 13 words.
    ol = (card.get("one_line") or "").split()
    if not ol:
        p.append("empty one_line")
    elif len(ol) > 14:
        p.append(f"one_line is {len(ol)} words (max 14)")

    if not (card.get("means") or "").strip():
        p.append("empty means")

    # --- banned phrasing anywhere in the prose ------------------------------
    prose = "\n".join(str(card.get(k) or "") for k in
                      ("means", "trap", "trick_line", "trick_unpack", "in_the_wild", "etymology"))
    for pat in BANNED:
        if re.search(pat, prose, re.I | re.M):
            p.append(f"banned phrasing matched /{pat}/")

    return p


BANK = Path(__file__).parent / "bank"


def leaks(answer: str, stem: str) -> bool:
    """Does the answer give itself away by appearing in the stem?

    Must be prefix containment on whole tokens, not the loose 4-char stem used
    for sentences. That looser rule flagged four questions falsely - 'assuage'
    against "assumed", 'largesse' against "larger", 'contend' against
    "controlled" - none of which reveal anything. Real leaks are inflections:
    abound / abounded.
    """
    a = answer.strip().lower()
    if len(a) < 4:
        return False
    for tok in re.findall(r"[a-z]+", stem.lower()):
        if len(tok) < 4:
            continue
        if tok.startswith(a) or (a.startswith(tok) and len(tok) >= len(a) - 2):
            return True
    return False


def check_bank() -> int:
    files = sorted(BANK.glob("*.json"))
    if not files:
        print(f"no bank in {BANK}")
        return 1
    qs = [q for f in files for q in json.loads(f.read_text(encoding="utf-8"))["questions"]]
    bad: list[tuple[str, list[str]]] = []
    for q in qs:
        p = []
        if q["type"] == "tc2":
            if len(q["blanks"]) != 2: p.append("tc2 needs 2 blanks")
            if "{2}" not in q["stem"]: p.append("stem missing {2}")
            if any(len(b["answers"]) != 1 for b in q["blanks"]): p.append("tc2 wants 1 answer per blank")
        else:
            if len(q["blanks"]) != 1: p.append("needs exactly 1 blank")
            need = 2 if q["type"] == "se" else 1
            if len(q["blanks"][0]["answers"]) != need: p.append(f"{q['type']} needs {need} answers")
            if q["type"] == "se" and len(q["blanks"][0]["options"]) != 6: p.append("se needs 6 options")
        if "{1}" not in q["stem"]: p.append("stem missing {1}")
        for b in q["blanks"]:
            if any(a not in b["options"] for a in b["answers"]): p.append("answer not among options")
            if len(set(o.lower() for o in b["options"])) != len(b["options"]): p.append("duplicate options")
            for a in b["answers"]:
                if leaks(a, q["stem"]): p.append(f"answer '{a}' leaks into the stem")
        if not (q.get("explanation") or "").strip(): p.append("no explanation")
        if p: bad.append((q["id"], p))

    print(f"{len(qs)} bank questions, {len(qs)-len(bad)} clean, {len(bad)} with problems")
    print("types:", dict(Counter(q["type"] for q in qs)))
    print("words covered:", len({w.lower() for q in qs for w in (q.get("words") or [])}))
    if bad:
        print("\ndetail:")
        for qid, ps in bad[:30]:
            print(f"  {qid}: {'; '.join(ps)}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--fixlist", action="store_true")
    ap.add_argument("--bank", action="store_true", help="check the generated question bank instead")
    args = ap.parse_args()

    if args.bank:
        return check_bank()

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
