"""
Pull the word list out of the GregMat xlsx into words.json.

The 'Word List' sheet is a grid, not a table: groups sit in column-pairs
(col A = Group 1, col C = Group 2, ...) and wrap into horizontal bands further
down the sheet. So we scan every cell for a 'Group N' header and read downward
from it until the column runs dry.

The 'Word Forms' sheet is a normal table and gives noun/verb/adjective variants,
which we attach to each word as `forms`.
"""

import json
import re
import sys
from pathlib import Path

import openpyxl

OUT = Path(__file__).parent / "words.json"


def find_source() -> Path:
    """Path to the xlsx: argv[1], else the newest matching file in Downloads."""
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    downloads = Path.home() / "Downloads"
    hits = sorted(downloads.glob("*Vocab List*.xlsx"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if not hits:
        sys.exit(f"No '*Vocab List*.xlsx' in {downloads}.\n"
                 f"Pass the path explicitly:  python extract_words.py <file.xlsx>")
    return hits[0]

GROUP_RE = re.compile(r"^\s*Group\s+(\d+)\s*$", re.I)
SKIP_RE = re.compile(r"^\s*Take Test", re.I)


def clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def main():
    src = find_source()
    print(f"reading {src.name}")
    wb = openpyxl.load_workbook(src, data_only=True)

    # ---- pass 1: locate every "Group N" header cell -------------------------
    ws = wb["Word List"]
    grid = [[clean(c) for c in row] for row in ws.iter_rows(values_only=True)]

    headers = []  # (group_no, row_idx, col_idx)
    for r, row in enumerate(grid):
        for c, val in enumerate(row):
            if val and (m := GROUP_RE.match(val)):
                headers.append((int(m.group(1)), r, c))

    # ---- pass 2: read downward from each header -----------------------------
    groups: dict[int, list[str]] = {}
    for gno, r, c in headers:
        words = []
        for rr in range(r + 1, len(grid)):
            val = grid[rr][c] if c < len(grid[rr]) else None
            if val is None:
                # One blank row can be padding; two means the column is done.
                nxt = grid[rr + 1][c] if rr + 1 < len(grid) and c < len(grid[rr + 1]) else None
                if nxt is None:
                    break
                continue
            if SKIP_RE.match(val) or GROUP_RE.match(val):
                if GROUP_RE.match(val):
                    break
                continue
            words.append(val)
        groups[gno] = words

    # The 'Word Forms' sheet is deliberately ignored - the Word List sheet is
    # the authoritative source.

    # ---- assemble -----------------------------------------------------------
    records, seen = [], {}
    for gno in sorted(groups):
        for w in groups[gno]:
            key = w.lower()
            if key in seen:
                seen[key]["groups"].append(gno)   # a word can repeat across groups
                continue
            rec = {"word": w, "groups": [gno]}
            seen[key] = rec
            records.append(rec)

    OUT.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"groups found : {len(groups)}  (numbers {min(groups)}-{max(groups)})")
    print(f"unique words : {len(records)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
