"""
Generate a bank of exam-format quiz questions from the cards and groups.

The app's built-in questions are assembled from data and are therefore always
correct, but bounded: each word has two sentences, so cloze repeats quickly, and
templates cannot produce the two formats the GRE actually uses.

This produces those, offline, once:

    tc2    two-blank Text Completion - one sentence, two interacting blanks,
           three options each. The real exam format.
    se     Sentence Equivalence - six options, pick the TWO that yield
           equivalent sentences.
    cloze  single blank, five options - same format the app already has, but
           in fresh contexts rather than the card's own two sentences.

Generation is per GROUP rather than per word. Sentence Equivalence structurally
needs a cluster of near-synonyms, which is exactly what a group is, and it
halves the cost.

Every question is then VERIFIED by an independent blind re-solve: a second call
sees the stem and options but not the intended answer, has to solve it, and has
to judge whether exactly one answer is defensible. Only questions where it
agrees on both are kept. This is the check that catches the failure that would
actually erode trust - a question where two options both genuinely fit and you
get marked wrong for a defensible choice.

    python quizgen.py --pilot 2           # 2 groups, print the results
    python quizgen.py --kinds meaning     # a whole grouping kind
    python quizgen.py                     # everything remaining
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

HERE = Path(__file__).parent
CARDS = HERE / "cards"
GROUPS = HERE / "groups"
BANK = HERE / "bank"

_lock = threading.Lock()


def log(m: str) -> None:
    with _lock:
        print(m, flush=True)


# ---------------------------------------------------------------------------
# One shape for all three types, so the app renders them with one code path.
# A blank carries `answers` as a list: length 1 for cloze and each TC blank,
# length 2 for Sentence Equivalence.
# ---------------------------------------------------------------------------

GEN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["questions"],
    "properties": {"questions": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["type", "stem", "blanks", "words", "explanation"],
        "properties": {
            "type": {"type": "string", "enum": ["tc2", "se", "cloze"]},
            "stem": {"type": "string", "description":
                     "The sentence with blanks written as {1} and, for tc2, {2}. "
                     "No markdown, no bolding, no answer anywhere in the text."},
            "blanks": {"type": "array", "minItems": 1, "maxItems": 2, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["options", "answers"],
                "properties": {
                    "options": {"type": "array", "minItems": 3, "maxItems": 6,
                                "items": {"type": "string"}},
                    "answers": {"type": "array", "minItems": 1, "maxItems": 2,
                                "items": {"type": "string"},
                                "description": "Must appear verbatim in options."},
                }}},
            "words": {"type": "array", "items": {"type": "string"},
                      "description": "Target words from the group this question trains."},
            "explanation": {"type": "string", "description":
                            "Two or three sentences: why the answer fits and why the "
                            "nearest wrong option does not. Name the distinction."},
        }}}},
}

VERIFY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["answers", "unique", "confidence", "problem"],
    "properties": {
        "answers": {"type": "array", "items": {"type": "string"},
                    "description": "Your own answer(s), copied verbatim from the options. "
                                   "One per blank for tc2/cloze; exactly two for se."},
        "unique": {"type": "boolean", "description":
                   "True only if EXACTLY one answer set is defensible. False if another "
                   "option also genuinely fits the sentence."},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "problem": {"type": ["string", "null"], "description":
                    "If unique is false or the question is broken, say what is wrong. "
                    "Else null."},
    },
}

GEN_SYSTEM = """You write practice questions for the GRE verbal section, for a
serious test-taker who already has good study notes on every word.

You will be given one group of related words with each word's study card. Write
questions in these formats:

tc2 - Text Completion, two blanks. ONE sentence (or two closely joined clauses)
  containing {1} and {2}. Three options per blank. The blanks must INTERACT: the
  sentence must supply enough logical structure that each blank is determined.
  This is the real exam format and the most valuable thing you produce.

se - Sentence Equivalence. One sentence with a single blank {1}, SIX options, and
  EXACTLY TWO correct ones that produce sentences of equivalent meaning. The two
  correct options must be near-synonyms of each other IN THIS CONTEXT. The four
  wrong options must be individually plausible - at least two should be words that
  fit the sentence grammatically and tonally but change its meaning.

cloze - One blank {1}, five options, one answer. Fresh context, not a sentence
  from the card.

Rules that decide whether a question is usable:

1. EXACTLY ONE answer set may be defensible. This is the one that matters. If a
   second option also genuinely fits, the question is broken - a real test-taker
   picking it would be right and you would mark them wrong. When in doubt, add
   more constraining context to the sentence rather than hoping.
2. The sentence must CONSTRAIN the answer. A blank that merely accepts the word
   teaches nothing; the sentence must make the word necessary, through contrast,
   cause, concession or example.
3. Draw wrong options from the group's own words where possible. Distractors that
   are near-synonyms are the whole point; unrelated words make it trivial.
4. Never put the answer, or an obvious morphological variant of it, elsewhere in
   the stem.
5. Write real sentences on real subjects - history, science, criticism, politics,
   biography. The GRE's register is adult and formal. No "the student was very
   ___" filler.
6. `answers` must reproduce the option strings verbatim.

Cover the group's words rather than writing three questions about one word."""

VERIFY_SYSTEM = """You are checking a GRE practice question. You are NOT told the
intended answer. Solve it yourself, then judge whether it is usable.

Return:
  answers    - your own answer, copied verbatim from the options. One per blank
               for a two-blank question; exactly two for Sentence Equivalence.
  unique     - true ONLY if exactly one answer set is defensible. Set it FALSE if
               any other option also genuinely fits the sentence. Be strict: this
               check exists to catch questions where a reasonable test-taker
               picks a defensible option and is marked wrong. If you can argue
               for a second option, it is not unique.
  confidence - how sure you are of your own answer.
  problem    - what is wrong, when something is. Otherwise null.

Judge the sentence as written. Do not be charitable about missing context: if the
sentence does not actually constrain the blank, that is exactly the defect you
are here to find."""


def load_groups(kinds: list[str] | None) -> list[dict]:
    out = []
    for f in sorted(GROUPS.rglob("*.json")):
        try:
            g = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if g.get("core") and g.get("words") and (not kinds or g["kind"] in kinds):
            out.append(g)
    return out


def card_index() -> dict[str, dict]:
    return {c["word"].lower(): c
            for c in (json.loads(f.read_text(encoding="utf-8"))
                      for f in sorted(CARDS.glob("*.json")))}


def semantic_neighbours(word: str, sem: list[dict], limit: int = 4) -> list[str]:
    """Lines describing the near-synonyms of `word`, drawn from the 655 semantic
    groups. A GregMat group is an arbitrary study batch, so Sentence Equivalence
    cannot find its second correct answer inside it - this is where that material
    comes from."""
    out = []
    for g in sem:
        me = next((m for m in g["words"] if m["word"].lower() == word.lower()), None)
        if not me:
            continue
        others = [m["word"] for m in g["words"] if m["word"].lower() != word.lower()]
        out.append(f"  [{g['kind']}] {g['title']}: {', '.join(others)}")
        if g["kind"] == "meaning" and me.get("nuance"):
            out.append(f"      how {word} differs: {me['nuance']}")
        if len(out) >= limit * 2:
            break
    return out


def gregmat_prompt(gno: int, batch: list[dict], cards: dict,
                   sem_by_word: dict[str, list[dict]], n: int) -> str:
    """One prompt per batch of words from a single GregMat group."""
    parts = [f"GREGMAT GROUP {gno} — write {n} questions, roughly one per word below.",
             "",
             "The TARGET word of each question must come from this list, because these "
             "are the words being studied this week. Distractors, and the second correct "
             "answer in a Sentence Equivalence item, should be drawn from the near-synonyms "
             "listed under each word - those are its genuine confusables, and unrelated "
             "distractors make a question trivial.",
             "", "--- WORDS ---", ""]
    for c in batch:
        parts.append(f"### {c['word']} ({c.get('pos','')})")
        parts.append(f"{c.get('one_line','')}")
        parts.append(f"connotation: {c.get('connotation','')} | register: {c.get('register','')}")
        parts.append((c.get("means") or "").strip())
        nb = semantic_neighbours(c["word"], sem_by_word.get(c["word"].lower(), []))
        if nb:
            parts.append("near-synonyms and confusables:")
            parts += nb
        parts.append("")
    return "\n".join(parts)


def group_prompt(g: dict, cards: dict, n: int) -> str:
    parts = [f"GROUP ({g['kind']}): {g['title']}", "", g["core"], "",
             f"Write {n} questions: roughly half tc2, a third se, the rest cloze.",
             "", "--- WORDS ---", ""]
    for m in g["words"]:
        c = cards.get(m["word"].lower())
        parts.append(f"### {m['word']}")
        if c:
            parts.append(f"{c.get('pos','')} — {c.get('one_line','')}")
            parts.append(f"connotation: {c.get('connotation','')} | register: {c.get('register','')}")
            parts.append((c.get("means") or "").strip())
        parts.append(f"nuance within this group: {m.get('nuance','')}")
        parts.append("")
    return "\n".join(parts)


def render_for_verify(q: dict) -> str:
    lines = [f"TYPE: {q['type']}", "", q["stem"], ""]
    for i, b in enumerate(q["blanks"], 1):
        lines.append(f"Blank {{{i}}} options: " + " | ".join(b["options"]))
    if q["type"] == "se":
        lines.append("(Sentence Equivalence: choose exactly TWO.)")
    return "\n".join(lines)


def norm(xs) -> list[str]:
    return sorted(x.strip().lower() for x in xs)


_BLANK_FORMS = [
    (r"\(\s*i{1,2}\s*\)", None),        # (i) (ii)
    (r"\{\{\s*(\d)\s*\}\}", None),      # {{1}}
    (r"_{3,}", None),                   # ____
    (r"\[\s*(\d)\s*\]", None),          # [1]
    (r"<\s*(\d)\s*>", None),            # <1>
]


def normalise_stem(q: dict) -> dict:
    """Rewrite whatever blank notation the model used into {1}/{2}.

    The prompt asks for {1} and {2}, and mostly gets them, but a model that
    writes "(i) ... (ii)" or "_____" instead is producing a perfectly good
    question in the wrong notation. Rejecting those threw away work already paid
    for - one pilot batch lost five of eight questions this way.
    """
    import re
    stem = q.get("stem") or ""
    if "{1}" in stem and (q["type"] != "tc2" or "{2}" in stem):
        return q
    for pat, _ in _BLANK_FORMS:
        if re.search(pat, stem):
            n = [0]
            def repl(_m):
                n[0] += 1
                return "{%d}" % n[0]
            stem = re.sub(pat, repl, stem)
            break
    q["stem"] = stem
    return q


def process_unit(unit_id: str, prompt: str, n: int) -> tuple[list[dict], dict]:
    """Generate then blind-verify one batch. Returns (kept_questions, stats)."""
    data, u1 = claude_cli.call(GEN_SYSTEM, prompt, GEN_SCHEMA, timeout=1500)
    raw = data.get("questions", [])
    kept, stats = [], {"made": len(raw), "kept": 0, "rejected": 0,
                       "cost": (u1.get("cost") or 0), "rejects": []}

    for i, q in enumerate(raw):
        # Structural checks first - cheaper than a model call.
        q = normalise_stem(q)
        try:
            if q["type"] == "tc2" and len(q["blanks"]) != 2: raise ValueError("tc2 needs 2 blanks")
            if q["type"] in ("se", "cloze") and len(q["blanks"]) != 1: raise ValueError("needs 1 blank")
            if q["type"] == "se":
                b = q["blanks"][0]
                if len(b["options"]) != 6 or len(b["answers"]) != 2: raise ValueError("se needs 6 options / 2 answers")
            for b in q["blanks"]:
                for a in b["answers"]:
                    if a not in b["options"]: raise ValueError(f"answer {a!r} not among options")
            need = 2 if q["type"] == "se" else 1
            for b in q["blanks"]:
                if len(b["answers"]) != need: raise ValueError("wrong answer count")
            if "{1}" not in q["stem"]: raise ValueError("stem has no {1}")
            if q["type"] == "tc2" and "{2}" not in q["stem"]: raise ValueError("stem has no {2}")
        except Exception as e:  # noqa: BLE001
            stats["rejected"] += 1
            stats["rejects"].append({"why": f"structure: {e}", "q": q})
            continue

        try:
            v, u2 = claude_cli.call(VERIFY_SYSTEM, render_for_verify(q), VERIFY_SCHEMA, timeout=900)
            stats["cost"] += (u2.get("cost") or 0)
        except Exception as e:  # noqa: BLE001
            stats["rejected"] += 1
            stats["rejects"].append({"why": f"verify call failed: {e}", "q": q})
            continue

        expected = norm([a for b in q["blanks"] for a in b["answers"]])
        if norm(v.get("answers", [])) != expected:
            stats["rejected"] += 1
            stats["rejects"].append({"why": "verifier answered differently: "
                                            f"{v.get('answers')} vs {expected}",
                                     "problem": v.get("problem"), "q": q})
            continue
        if not v.get("unique") or v.get("confidence") == "low":
            stats["rejected"] += 1
            stats["rejects"].append({"why": f"not unique / low confidence",
                                     "problem": v.get("problem"), "q": q})
            continue

        q["id"] = f"{unit_id}__{q['type']}__{i:02d}"
        q["unit"] = unit_id
        q["verified"] = True
        kept.append(q)

    stats["kept"] = len(kept)
    return kept, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", nargs="+", type=int,
                    help="GregMat group numbers, e.g. --groups 1 2 3. Default: all 38.")
    ap.add_argument("--per-batch", type=int, default=4,
                    help="words per call. Kept small on purpose: one long response "
                         "degrades toward the end, same reason cards are a loop.")
    ap.add_argument("--per-word", type=int, default=2,
                    help="questions to request per word (batch of 4 x 2 = 8 per call)")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--print", dest="show", action="store_true",
                    help="print every kept question (use for pilots)")
    args = ap.parse_args()

    BANK.mkdir(exist_ok=True)
    cards = card_index()

    # Semantic groups indexed by word - these supply the near-synonyms that make
    # a distractor hard and make Sentence Equivalence possible at all.
    sem_by_word: dict[str, list[dict]] = {}
    for g in load_groups(None):
        for m in g["words"]:
            sem_by_word.setdefault(m["word"].lower(), []).append(g)

    by_gregmat: dict[int, list[dict]] = {}
    for c in cards.values():
        for gno in (c.get("groups") or []):
            by_gregmat.setdefault(gno, []).append(c)
    for v in by_gregmat.values():
        v.sort(key=lambda c: c["word"].lower())

    wanted = sorted(args.groups) if args.groups else sorted(by_gregmat)

    units = []
    for gno in wanted:
        words = by_gregmat.get(gno, [])
        for bi in range(0, len(words), args.per_batch):
            batch = words[bi:bi + args.per_batch]
            uid = f"gregmat{gno:02d}__b{bi // args.per_batch}"
            if not args.force and (BANK / f"{uid}.json").exists():
                continue
            units.append((uid, gno, batch))

    if not units:
        log("nothing to do (use --force to regenerate)")
        return 0

    total_words = sum(len(b) for _, _, b in units)
    log(f"target {total_words * args.per_word} questions "
        f"({args.per_word} per word)")
    log(f"{len(wanted)} GregMat group(s), {total_words} words, "
        f"{len(units)} batches x {args.per_batch * args.per_word} questions\n")

    tot = {"made": 0, "kept": 0, "rejected": 0, "cost": 0.0}
    started = time.time()

    def work(unit):
        uid, gno, batch = unit
        want = len(batch) * args.per_word
        prompt = gregmat_prompt(gno, batch, cards, sem_by_word, want)
        kept, st = process_unit(uid, prompt, want)
        for q in kept:
            q["gregmat_group"] = gno
        (BANK / f"{uid}.json").write_text(json.dumps(
            {"unit": uid, "gregmat_group": gno,
             "words": [c["word"] for c in batch],
             "questions": kept,
             "rejects": [{"why": r["why"], "problem": r.get("problem"),
                          "stem": r["q"].get("stem")} for r in st["rejects"]]},
            indent=2, ensure_ascii=False), encoding="utf-8")
        return uid, gno, kept, st

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(work, u): u for u in units}
        for fut in as_completed(futs):
            try:
                uid, gno, kept, st = fut.result()
            except Exception as e:  # noqa: BLE001
                log(f"  FAIL {futs[fut][0]}: {e}")
                continue
            for k in ("made", "kept", "rejected", "cost"):
                tot[k] += st[k]
            log(f"  {uid:<22} {st['kept']}/{st['made']} kept   ${tot['cost']:6.2f}")
            if args.show:
                for q in kept:
                    print("\n" + "=" * 74)
                    print(f"[{q['type']}]  group {gno}  ->  {', '.join(q.get('words') or [])}")
                    print(q["stem"])
                    for i, b in enumerate(q["blanks"], 1):
                        print(f"  ({i}) " + "  |  ".join(b["options"]))
                        print(f"      answer: {', '.join(b['answers'])}")
                    print("  " + q["explanation"])
                for r in st["rejects"]:
                    print(f"\n  [REJECTED] {r['why']}"
                          + (f" — {r['problem']}" if r.get("problem") else ""))

    rate = tot["kept"] / max(tot["made"], 1)
    log(f"\n{tot['kept']} kept of {tot['made']} ({rate:.0%}), "
        f"{tot['rejected']} rejected, {(time.time()-started)/60:.1f} min, ${tot['cost']:.2f}")
    if tot["kept"]:
        log(f"${tot['cost']/tot['kept']:.3f} per usable question")
    return 0


if __name__ == "__main__":
    sys.exit(main())
