#!/usr/bin/env python3
"""Convert the GregMat flashcard images into the repo, and index them.

    python flashcards.py [source-folder]

Source is a folder of `Day NN/NN - word.jpg`, 1920x1080 each, about 110 MB for
the full 1020. They are re-encoded to 1000px WebP, which brings the set to
roughly 19 MB - small enough to commit and to bundle in the APK, so flashcards
work offline like the rest of the app.

1000px is deliberate: the card is never displayed wider than about 700px even
rotated on a tall phone, so this is already oversampled, and dropping further
starts to cost legibility on the example sentence, which is the smallest text
on the card.

Output:
    out/fc/<slug>.webp      one per word, slug matching cards/<slug>.json
    flashcards.json         word -> {"f": slug, "d": day}
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

from PIL import Image

HERE = pathlib.Path(__file__).parent
CARDS = HERE / "cards"
OUTDIR = HERE / "out" / "fc"
INDEX = HERE / "flashcards.json"

DEFAULT_SRC = pathlib.Path.home() / "Pictures" / "GregMat Vocab Flashcards"
WIDTH = 1000
QUALITY = 70


def slug(word: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", word.lower()).strip("_")


def main() -> int:
    src = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SRC
    if not src.exists():
        print(f"source not found: {src}")
        return 1

    known = {json.loads(p.read_text(encoding="utf-8"))["word"] for p in CARDS.glob("*.json")}
    by_lower = {w.lower(): w for w in known}

    OUTDIR.mkdir(parents=True, exist_ok=True)
    index: dict[str, dict] = {}
    skipped: list[str] = []
    done = 0

    for p in sorted(src.glob("Day */*.jpg")):
        m = re.match(r"(\d+)\s*-\s*(.+)\.jpg$", p.name, re.I)
        if not m:
            continue
        raw = m.group(2).strip()
        word = by_lower.get(raw.lower())
        if not word:                       # an image for a word we do not carry
            skipped.append(raw)
            continue
        day = int(re.search(r"Day\s*(\d+)", p.parent.name, re.I).group(1))
        s = slug(word)
        dest = OUTDIR / f"{s}.webp"
        if not dest.exists():
            im = Image.open(p).convert("RGB")
            im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
            im.save(dest, "WEBP", quality=QUALITY, method=6)
        index[word] = {"f": s, "d": day}
        done += 1
        if done % 200 == 0:
            print(f"  {done} converted", flush=True)

    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=0), encoding="utf-8")
    total = sum(f.stat().st_size for f in OUTDIR.glob("*.webp"))
    print(f"{len(index)}/{len(known)} words have a flashcard "
          f"({100 * len(index) / len(known):.0f}%)")
    print(f"{total / 1048576:.1f} MB in {OUTDIR}")
    if skipped:
        print(f"{len(skipped)} images had no matching card: {sorted(skipped)[:6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
