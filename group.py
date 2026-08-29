"""
Cross-word grouping analysis over the 1112 cards.

Groups are the thing a per-word card physically cannot give you: which words
crowd the same patch of meaning, and how they differ once they're side by side.

Three stages, run in order:

    python group.py mechanical    # deterministic: root families, lookalikes
    python group.py discover      # model proposes memberships for 5 schemes
    python group.py write         # one stateless call per group -> core + nuances
    python group.py render        # -> out/groups.md

Stage 1 needs no model at all - `root` and `confusables` were populated on every
card precisely so these fall out as graph problems.

Stages 2 and 3 are split deliberately. Discovery sees all 1112 words at once and
returns only membership lists, which is cheap. The write-up is then one
independent call per group, so a hundred groups are written to the same standard
rather than degrading down a single long response - the same reason card
generation is a loop.

Resumable throughout: one file per group under groups/.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import threading
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import claude_cli

HERE = Path(__file__).parent
CARDS = HERE / "cards"
GROUPS = HERE / "groups"
OUT = HERE / "out"

_lock = threading.Lock()


def log(m: str) -> None:
    with _lock:
        print(m, flush=True)


# ---------------------------------------------------------------------------
# schemes
# ---------------------------------------------------------------------------

SCHEMES = {
    "meaning": (
        "Near-synonym clusters: words that crowd the same patch of meaning and "
        "would all look plausible in the same blank.",
        "Group words that a test-taker could genuinely confuse because they mean "
        "almost the same thing. The whole value is the NUANCE that separates them. "
        "Aim for tight groups of 3-7, not loose thematic bins. A group of 12 is "
        "almost always two groups."),
    "second-meaning": (
        "Common words carrying a less familiar sense that the exam actually tests.",
        "Find ordinary words whose everyday meaning is NOT the tested one - champion "
        "(to advocate), check (to restrain), brook (to tolerate), base (ignoble), "
        "table, flag, partial. The danger is that the reader thinks they know the word "
        "and never looks twice. Group them by the KIND of shift."),
    "intensity": (
        "Scales: words on one dimension, ordered from weakest to strongest.",
        "Build ladders on a single dimension, ordered weak -> strong, e.g. "
        "unfortunate / detrimental / disastrous / calamitous. Order matters: the "
        "words array MUST run weakest first. Only build a scale where the ordering "
        "is genuinely defensible."),
    "connotation": (
        "Words whose charge is stronger or more one-sided than their definition suggests.",
        "Find words where the dictionary sense looks neutral but usage carries a clear "
        "positive or negative charge - the famous/notorious problem. These decide "
        "Sentence Equivalence questions. Group by the direction and kind of charge."),
    "antonym": (
        "Opposition clusters: words defined against their opposites.",
        "Group words with their genuine opposites - garrulous/laconic/taciturn, "
        "ascetic/hedonistic, ephemeral/enduring. Learning a word against its opposite "
        "fixes both. Each group should sit on one clear axis."),
}

DISCOVER_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["groups"],
    "properties": {"groups": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["title", "words"],
        "properties": {
            "title": {"type": "string", "description": "Short label, e.g. 'Complaining and peevish'."},
            "words": {"type": "array", "minItems": 3, "items": {"type": "string"},
                      "description": "3+ words, exactly as spelled in the index."},
        }}}},
}

WRITE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "core", "words", "exam_note"],
    "properties": {
        "title": {"type": "string"},
        "core": {"type": "string", "description":
                 "Markdown. The meaning ALL these words share - the thing that makes "
                 "them confusable. 2-4 sentences. Do not list the words here."},
        "words": {"type": "array", "minItems": 3, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["word", "nuance"],
            "properties": {
                "word": {"type": "string"},
                "nuance": {"type": "string", "description":
                           "One or two sentences: what THIS word adds or restricts "
                           "relative to the others. Must contrast, not re-define. "
                           "If it could be pasted under another word in the group, "
                           "it is too vague."}}}},
        "exam_note": {"type": ["string", "null"], "description":
                      "One line on how the GRE exploits this group, or null."},
    },
}

DISCOVER_SYSTEM = """You are building a GRE vocabulary study document for a serious test-taker.

You will receive an index of words, one per line, as:
    word | part of speech | one-line gloss | connotation | sense tags

Propose groups of a single requested kind. Return ONLY membership: a short title
and the member words. No prose, no explanations - a later pass writes those.

Hard rules:
- Every group has AT LEAST 3 words. Never 2.
- Use words EXACTLY as spelled in the index. Never invent a word not in it.
- A word may appear in more than one group when it genuinely belongs to both.
- Tight and specific beats large and vague. A sprawling group teaches nothing,
  because the whole point is the contrast between close neighbours.
- Cover the index thoroughly. Do not stop at a token handful - propose every
  group the data genuinely supports.
- Do not force a group. If words do not truly belong together, leave them out."""

WRITE_SYSTEM = """You are writing one section of a GRE vocabulary study document.

You get a group of words that belong together, with each word's full existing
study card. Write the section that makes their differences unmistakable.

`core`  - the meaning they SHARE. What makes these confusable in the first place.
          Two to four sentences. Do not list the words back.
`words` - for each word, the nuance that SEPARATES it from the others in THIS
          group. This is the entire value of the section, so it must contrast.
          Test every line: if it could be pasted under a different word in the
          same group, it is too vague and must be rewritten. Name the specific
          thing - who says it, how strong it is, what it implies about the
          speaker, what it attaches to.
`exam_note` - one line on how the exam exploits this group, or null.

Style: pithy and direct. Bold the word being discussed. No filler, no throat
clearing, no restating the definition the reader already has. Never invent a
sense a word does not have.

If the ordering of `words` carries meaning (an intensity scale), preserve the
order you are given unless it is clearly wrong, in which case fix it."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_cards() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(CARDS.glob("*.json"))]


def norm_root(r: str | None) -> str | None:
    if not r:
        return None
    r = r.split("(")[0].strip().lower().split(",")[0].strip()
    r = "".join(c for c in unicodedata.normalize("NFD", r) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z\- ]", "", r).strip() or None


def gid(kind: str, title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"{kind}__{s or 'group'}"


def save_group(rec: dict) -> None:
    d = GROUPS / rec["kind"]
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{rec['id']}.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def load_groups(kind: str | None = None) -> list[dict]:
    root = GROUPS / kind if kind else GROUPS
    if not root.exists():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(root.rglob("*.json"))]


def build_index(cards: list[dict]) -> str:
    lines = []
    for c in sorted(cards, key=lambda c: c["word"].lower()):
        lines.append(" | ".join([
            c["word"], c.get("pos", ""), (c.get("one_line") or "").replace("|", "/"),
            c.get("connotation", ""), ",".join(c.get("sense_tags") or []),
        ]))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# stage 1 - mechanical
# ---------------------------------------------------------------------------

def stage_mechanical(cards: list[dict]) -> None:
    by_word = {c["word"].lower(): c for c in cards}

    # root families
    fam = defaultdict(list)
    for c in cards:
        if (r := norm_root(c.get("root"))):
            fam[r].append(c["word"])
    n = 0
    for root, words in sorted(fam.items()):
        if len(words) < 3:
            continue
        n += 1
        raw = next((c.get("root") for c in cards
                    if norm_root(c.get("root")) == root and c.get("root")), root)
        save_group({"kind": "root", "id": gid("root", root), "title": f"Root: {raw}",
                    "seed_words": sorted(words), "auto": True})
    log(f"  root families      {n:>4} groups")

    # lookalikes - MUTUAL confusable edges only.
    # Confusability is not transitive: following one-way edges collapses 234
    # words into a single meaningless blob (abstain -> abstruse -> abstract -> ...).
    # Requiring both words to name each other is a far stronger signal and
    # produces clean components of 3-7.
    conf = {w: {x.lower().strip() for x in (c.get("confusables") or [])
                if x.lower().strip() in by_word and x.lower().strip() != w}
            for w, c in by_word.items()}
    mutual = {(a, b) for a, vs in conf.items() for b in vs if a < b and a in conf.get(b, set())}

    adj = defaultdict(set)
    for a, b in mutual:
        adj[a].add(b)
        adj[b].add(a)
    seen, comps = set(), []
    for w in adj:
        if w in seen:
            continue
        stack, comp = [w], set()
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            comp.add(x)
            stack += [y for y in adj[x] if y not in seen]
        comps.append(comp)

    n = 0
    for comp in comps:
        if len(comp) < 3:
            continue
        words = sorted(by_word[w]["word"] for w in comp)
        # Separate spelling lookalikes from words confused by meaning alone.
        pairs = [(a, b) for a, b in mutual if a in comp and b in comp]
        avg = sum(difflib.SequenceMatcher(None, a, b).ratio() for a, b in pairs) / max(len(pairs), 1)
        n += 1
        save_group({"kind": "lookalike", "id": gid("lookalike", words[0] + "-" + words[1]),
                    "title": " / ".join(words[:3]) + ("…" if len(words) > 3 else ""),
                    "seed_words": words, "similarity": round(avg, 2), "auto": True})
    log(f"  lookalike clusters {n:>4} groups  (from {len(mutual)} mutual edges)")


# ---------------------------------------------------------------------------
# stage 2 - discover
# ---------------------------------------------------------------------------

def stage_discover(cards: list[dict], only: list[str] | None) -> None:
    index = build_index(cards)
    valid = {c["word"].lower(): c["word"] for c in cards}
    log(f"  index: {len(cards)} words, {len(index):,} chars (sent on stdin)\n")

    for kind, (desc, guidance) in SCHEMES.items():
        if only and kind not in only:
            continue
        prompt = (f"GROUPING KIND: {kind}\n{desc}\n\n{guidance}\n\n"
                  f"--- INDEX ({len(cards)} words) ---\n{index}\n")
        t = time.time()
        try:
            data, usage = claude_cli.call(DISCOVER_SYSTEM, prompt, DISCOVER_SCHEMA, timeout=1800)
        except Exception as e:  # noqa: BLE001
            log(f"  {kind:<15} FAILED  {e}")
            continue

        kept = dropped = 0
        for g in data.get("groups", []):
            words, bad = [], []
            for w in g.get("words", []):
                (words if w.lower() in valid else bad).append(valid.get(w.lower(), w))
            words = sorted(set(words), key=words.index)
            if len(words) < 3:
                dropped += 1
                continue
            kept += 1
            save_group({"kind": kind, "id": gid(kind, g["title"]),
                        "title": g["title"], "seed_words": words,
                        "hallucinated": bad or None})
        log(f"  {kind:<15} {kept:>4} groups kept, {dropped} dropped "
            f"({time.time()-t:.0f}s, ${usage.get('cost',0):.2f})")


# ---------------------------------------------------------------------------
# stage 3 - write
# ---------------------------------------------------------------------------

def stage_write(cards: list[dict], workers: int, only: list[str] | None, force: bool) -> None:
    by_word = {c["word"].lower(): c for c in cards}
    todo = [g for g in load_groups()
            if (not only or g["kind"] in only) and (force or not g.get("core"))]
    if not todo:
        log("  nothing to write")
        return
    log(f"  {len(todo)} groups to write\n")

    def brief(word: str) -> str:
        c = by_word.get(word.lower())
        if not c:
            return f"### {word}\n(no card)"
        return (f"### {c['word']} ({c.get('pos','')})\n"
                f"gloss: {c.get('one_line','')}\n"
                f"connotation: {c.get('connotation','')} | register: {c.get('register','')}\n"
                f"{c.get('means','')}\n")

    totals = {"cost": 0.0}
    done = failed = 0
    started = time.time()

    def work(g: dict):
        words = g.get("seed_words") or []
        prompt = (f"GROUPING KIND: {g['kind']}\n"
                  f"PROVISIONAL TITLE: {g['title']}\n\n"
                  + ("The order below is an intensity ordering; preserve it unless wrong.\n\n"
                     if g["kind"] == "intensity" else "")
                  + "--- WORDS IN THIS GROUP ---\n\n"
                  + "\n".join(brief(w) for w in words))
        data, usage = claude_cli.call(WRITE_SYSTEM, prompt, WRITE_SCHEMA, timeout=1200)
        save_group({**g, **data, "kind": g["kind"], "id": g["id"]})
        return g["id"], usage

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(work, g): g for g in todo}
        for fut in as_completed(futs):
            g = futs[fut]
            try:
                _, u = fut.result()
                done += 1
                totals["cost"] += u.get("cost", 0) or 0
                n = done + failed
                rate = n / max(time.time() - started, 1e-9)
                log(f"  [{n:>4}/{len(todo)}] {g['id'][:52]:<52} ok  "
                    f"${totals['cost']:6.2f} eta {(len(todo)-n)/rate/60:4.1f}m")
            except Exception as e:  # noqa: BLE001
                failed += 1
                log(f"  [{done+failed:>4}/{len(todo)}] {g['id'][:52]:<52} FAIL {e}")

    log(f"\n  done {done}, failed {failed}, {(time.time()-started)/60:.1f} min, "
        f"${totals['cost']:.2f}")


# ---------------------------------------------------------------------------
# stage 4 - render
# ---------------------------------------------------------------------------

HEADINGS = {
    "meaning": ("Meaning clusters", "Words that crowd the same patch of meaning. The definitions overlap; the nuance is what separates them."),
    "lookalike": ("Lookalikes and false friends", "Words confused by sight or sound, not by meaning. Mixing these up is the cheapest way to lose a mark."),
    "root": ("Root families", "Words built from the same root. Learn the root once and the family comes with it."),
    "second-meaning": ("Second meanings", "Ordinary words whose tested sense is not the one you already know. The danger is that you never look twice."),
    "intensity": ("Intensity scales", "One dimension, ordered weakest to strongest. Sentence Equivalence often turns on exactly this."),
    "connotation": ("Connotation traps", "Words whose charge is stronger or more one-sided than the definition suggests."),
    "antonym": ("Opposites", "Words learned against their opposite, which fixes both at once."),
}
ORDER = ["meaning", "lookalike", "second-meaning", "intensity", "connotation", "antonym", "root"]


def stage_render() -> None:
    groups = [g for g in load_groups() if g.get("core")]
    if not groups:
        log("  no written groups yet - run: python group.py write")
        return
    OUT.mkdir(exist_ok=True)
    by_kind = defaultdict(list)
    for g in groups:
        by_kind[g["kind"]].append(g)

    parts = ["# Word groups\n",
             "Cards teach one word at a time. This is the part they can't do: "
             "what a word looks like standing next to its neighbours.\n"]
    for kind in ORDER:
        gs = sorted(by_kind.get(kind, []), key=lambda g: g["title"].lower())
        if not gs:
            continue
        head, blurb = HEADINGS[kind]
        parts.append(f"\n---\n\n## {head}\n\n*{blurb}*\n")
        for g in gs:
            # Explicit anchor keyed on the group id, not the heading text.
            # Heading text collides across kinds ("Deception" exists as both a
            # meaning cluster and a connotation group); the id is the filename,
            # so it is unique by construction and stable across regeneration.
            parts.append(f"\n<a id=\"{g['id']}\"></a>\n### {g['title']}\n\n{g['core'].strip()}\n")
            for w in g.get("words", []):
                parts.append(f"- **{w['word']}** — {w['nuance'].strip()}")
            if g.get("exam_note"):
                parts.append(f"\n> **On the exam:** {g['exam_note'].strip()}")
            parts.append("")
    dest = OUT / "groups.md"
    dest.write_text("\n".join(parts) + "\n", encoding="utf-8")
    counts = ", ".join(f"{k} {len(by_kind[k])}" for k in ORDER if by_kind.get(k))
    log(f"  {len(groups)} groups -> {dest}\n  {counts}")


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["mechanical", "discover", "write", "render", "stats"])
    ap.add_argument("--only", nargs="+", help="restrict to these grouping kinds")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true", help="rewrite groups that already have prose")
    args = ap.parse_args()

    GROUPS.mkdir(exist_ok=True)
    cards = load_cards()
    log(f"{len(cards)} cards loaded\n")

    if args.stage == "mechanical":
        stage_mechanical(cards)
    elif args.stage == "discover":
        stage_discover(cards, args.only)
    elif args.stage == "write":
        stage_write(cards, args.workers, args.only, args.force)
    elif args.stage == "render":
        stage_render()
    else:
        gs = load_groups()
        by = defaultdict(list)
        for g in gs:
            by[g["kind"]].append(g)
        covered = {w.lower() for g in gs for w in (g.get("seed_words") or [])}
        for k in ORDER:
            if by.get(k):
                written = sum(1 for g in by[k] if g.get("core"))
                sizes = [len(g.get("seed_words") or []) for g in by[k]]
                log(f"  {k:<15} {len(by[k]):>4} groups ({written} written), "
                    f"sizes {min(sizes)}-{max(sizes)}, median {sorted(sizes)[len(sizes)//2]}")
        log(f"\n  {len(covered)}/{len(cards)} words appear in at least one group "
            f"({len(covered)/len(cards):.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
