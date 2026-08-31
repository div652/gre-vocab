"""
Export the cards as a TSV that Anki can import.

The app has its own spaced-repetition scheduler, which is fine, but it is
per-device and only syncs when you export/import by hand. Anki's scheduler is
far better tested and syncs across phone and desktop for free, so it is worth
having the option.

    python export_anki.py             # -> out/anki.tsv  (front/back/tags)
    python export_anki.py --minimal   # word -> one-line gloss only

Importing:
  Anki -> File -> Import -> out/anki.tsv
  Field separator: Tab.  Allow HTML in fields: YES  (otherwise it imports as
  literal <b> tags).  Map column 1 -> Front, 2 -> Back, 3 -> Tags.

Tags carry the GregMat group (g07), the register, the connotation and every
meaning/lookalike/etc. group the word belongs to, so you can build filtered
decks like "tag:lookalike" or "tag:connotation::negative".
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
CARDS = HERE / "cards"
GROUPS = HERE / "groups"
OUT = HERE / "out"


def md_to_html(s: str) -> str:
    """Just enough markdown for Anki fields."""
    if not s:
        return ""
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", s)
    return s.replace("\n\n", "<br><br>").replace("\n", "<br>")


def tag(s: str) -> str:
    """Anki tags cannot contain spaces."""
    return re.sub(r"[^A-Za-z0-9:_-]+", "-", s.strip()).strip("-").lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minimal", action="store_true",
                    help="word -> one-line gloss only, no card body")
    args = ap.parse_args()

    cards = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(CARDS.glob("*.json"))]
    if not cards:
        print(f"no cards in {CARDS}")
        return 1

    # word -> the groups it belongs to, for tagging
    gtags: dict[str, list[str]] = {}
    for f in sorted(GROUPS.rglob("*.json")):
        try:
            g = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not g.get("core"):
            continue
        for m in g.get("words", []):
            gtags.setdefault(m["word"].lower(), []).append(f"{g['kind']}::{tag(g['title'])[:40]}")

    OUT.mkdir(exist_ok=True)
    dest = OUT / ("anki-minimal.tsv" if args.minimal else "anki.tsv")
    rows = 0

    with dest.open("w", encoding="utf-8", newline="") as fh:
        for c in sorted(cards, key=lambda c: c["word"].lower()):
            w = c["word"]
            front = f"<b>{html.escape(w)}</b>"
            if c.get("pron"):
                front += f"<br><span style='color:#7aa2f7'>{html.escape(c['pron'])}</span>"

            if args.minimal:
                back = html.escape(c.get("one_line") or "")
            else:
                parts = [f"<b>{html.escape(c.get('one_line') or '')}</b>", md_to_html(c.get("means") or "")]
                if c.get("trap"):
                    parts.append(md_to_html(c["trap"]))
                if c.get("trick_line"):
                    t = f"<i>{md_to_html(c['trick_line'])}</i>"
                    if c.get("trick_unpack"):
                        t += "<br>" + md_to_html(c["trick_unpack"])
                    parts.append(t)
                for i, s in enumerate(c.get("sentences") or [], 1):
                    parts.append(f"{i}. {md_to_html(s)}")
                if c.get("in_the_wild"):
                    parts.append(md_to_html(c["in_the_wild"]))
                if c.get("etymology"):
                    parts.append(md_to_html(c["etymology"]))
                back = "<hr>".join(p for p in parts if p)

            tags = [f"g{g:02d}" for g in (c.get("groups") or [])]
            if c.get("register"):
                tags.append(f"register::{tag(c['register'])}")
            if c.get("connotation"):
                tags.append(f"connotation::{tag(c['connotation'])}")
            tags += gtags.get(w.lower(), [])

            # Tabs and newlines are the record separators, so they cannot survive
            # inside a field.
            cols = [x.replace("\t", " ").replace("\r", "").replace("\n", " ")
                    for x in (front, back, " ".join(dict.fromkeys(tags)))]
            fh.write("\t".join(cols) + "\n")
            rows += 1

    print(f"{rows} notes -> {dest}  ({dest.stat().st_size/1024:.0f} KB)")
    print("Anki: File > Import, separator Tab, ALLOW HTML IN FIELDS, "
          "map col1=Front col2=Back col3=Tags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
