"""
Render card JSON back into the approved markdown card format.

The JSON is the source of truth; this is one view over it (Slite/Notion get
pasted from here). The flashcard app will be another view over the same files.

Section order is fixed and matches the calibrated format:
    heading -> Means -> Trick to lock it in -> In sentences -> In the wild -> Where it comes from
A section whose field is null is omitted entirely - never rendered as an empty
heading, and never rendered as a note explaining its own absence.

    python render.py                        # cards/ -> out/group_01.md ... group_38.md
    python render.py --words accord phony    # print those cards to stdout
    python render.py --single                # one combined out/all.md
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
CARDS = HERE / "cards"
GROUPS = HERE / "groups"
OUT = HERE / "out"

KIND_ORDER = ["meaning", "lookalike", "second-meaning", "intensity",
              "connotation", "antonym", "root"]
KIND_LABEL = {
    "meaning": "Meaning cluster", "lookalike": "Lookalike",
    "second-meaning": "Second meaning", "intensity": "Intensity scale",
    "connotation": "Connotation", "antonym": "Opposites", "root": "Root family",
}


def load_group_index() -> dict[str, list[dict]]:
    """word (lowercased) -> the written groups it belongs to.

    Only groups with prose are indexed; a discovered-but-unwritten group would
    link to a heading that does not exist in groups.md.
    """
    idx: dict[str, list[dict]] = {}
    if not GROUPS.exists():
        return idx
    for f in sorted(GROUPS.rglob("*.json")):
        try:
            g = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not g.get("core") or not g.get("words"):
            continue
        for w in g["words"]:
            idx.setdefault(w["word"].lower(), []).append(g)
    for v in idx.values():
        v.sort(key=lambda g: (KIND_ORDER.index(g["kind"]) if g["kind"] in KIND_ORDER else 99,
                              g["title"].lower()))
    return idx


def render(card: dict, group_idx: dict[str, list[dict]] | None = None,
           groups_href: str = "groups.md") -> str:
    w, pos, pron = card["word"], card.get("pos", ""), card.get("pron", "")

    head = f"# **{w}**"
    if pos:
        head += f" *({pos})*"
    if pron:
        head += f" — **{pron}**"

    parts = [head]
    if card.get("pron_note"):
        parts.append(f"*{card['pron_note'].strip('*')}*")

    means = (card.get("means") or "").strip()
    if card.get("trap"):
        means += "\n\n" + card["trap"].strip()
    parts.append("### Means\n" + means)

    if card.get("trick_line"):
        block = "### Trick to lock it in\n> " + card["trick_line"].lstrip("> ").strip()
        if card.get("trick_unpack"):
            block += "\n\n" + card["trick_unpack"].strip()
        parts.append(block)

    sents = card.get("sentences") or []
    if sents:
        parts.append("### In sentences\n" +
                     "\n".join(f"{i}. {s.strip()}" for i, s in enumerate(sents, 1)))

    if card.get("in_the_wild"):
        parts.append("### In the wild\n" + card["in_the_wild"].strip())

    if card.get("etymology"):
        parts.append("### Where it comes from\n" + card["etymology"].strip())

    # Last section on the card: where else this word turns up. One line per
    # group, linked into groups.md, so you can follow a word sideways into its
    # neighbourhoods when you want to go deeper.
    for g in (group_idx or {}).get(card["word"].lower(), []):
        label = KIND_LABEL.get(g["kind"], g["kind"])
        others = [m["word"] for m in g["words"]
                  if m["word"].lower() != card["word"].lower()]
        if "### Also sits in" not in (parts[-1] if parts else ""):
            parts.append("### Also sits in")
        parts[-1] += (f"\n- **{label}** · [{g['title']}]({groups_href}#{g['id']})"
                      + (f" — with *{', '.join(others)}*" if others else ""))

    return "\n\n".join(parts)


def load_all() -> list[dict]:
    out = []
    for f in sorted(CARDS.glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            print(f"skipping unreadable {f.name}: {e}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", nargs="+", help="print these cards to stdout instead of writing files")
    ap.add_argument("--single", action="store_true", help="one combined out/all.md")
    args = ap.parse_args()

    cards = load_all()
    gidx = load_group_index()
    if not cards:
        print(f"no cards in {CARDS}")
        return 1

    if args.words:
        want = {w.lower() for w in args.words}
        for c in cards:
            if c["word"].lower() in want:
                print(render(c, gidx) + "\n\n---\n")
        return 0

    OUT.mkdir(exist_ok=True)
    sep = "\n\n---\n\n"

    if args.single:
        body = sep.join(render(c, gidx) for c in sorted(cards, key=lambda c: c["word"].lower()))
        (OUT / "all.md").write_text(body + "\n", encoding="utf-8")
        print(f"wrote {OUT / 'all.md'} ({len(cards)} cards)")
        return 0

    by_group: dict[int, list[dict]] = defaultdict(list)
    for c in cards:
        for g in c.get("groups") or [0]:
            by_group[g].append(c)

    for g in sorted(by_group):
        items = sorted(by_group[g], key=lambda c: c["word"].lower())
        body = f"# Group {g}\n\n" + sep.join(render(c, gidx) for c in items)
        (OUT / f"group_{g:02d}.md").write_text(body + "\n", encoding="utf-8")
        print(f"group_{g:02d}.md  {len(items):>3} cards")

    print(f"\n{len(cards)} cards -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
