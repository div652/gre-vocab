#!/usr/bin/env python3
"""Collect the TC/SE signal phrases into phrases.json.

    python phrases.py <source> [<source> ...]

A source is either a local .xlsx or a Google Sheets id/URL (exported as xlsx).
Both of the owner's sources are built in, so plain `python phrases.py` with no
arguments does the right thing.

WHAT A SOURCE LOOKS LIKE
------------------------
Two shapes, both handled:

* a sheet with the type in its own column - `phrase | type | sentence`
* a sheet whose NAME is the type - `phrase | sentence` - which is why SHEETS
  maps sheet names to types rather than guessing from the content

Punctuation is deliberately excluded: a semicolon is a signal, but it is not a
thing you can put on the front of a flashcard and recall.

Workbooks are gitignored (paid material); phrases.json is committed.
"""
from __future__ import annotations

import io
import json
import pathlib
import re
import sys
import urllib.request

import openpyxl

HERE = pathlib.Path(__file__).parent
OUT = HERE / "phrases.json"

# Sheet name -> what the phrases in it signal. None means "the sheet carries a
# type column of its own"; SKIP means leave the sheet alone.
SKIP = object()
SHEETS = {
    "all phrases": None,
    "support phrases": "Support",
    "support words": "Support",
    "contrast phrases": "Contrast",
    "contrast words": "Contrast",
    "words that dont change the logi": "Logic Unchanged",
    "words that don't change the logic": "Logic Unchanged",
    'words that mean "not" or "no"': "Not / No",
    "support punctuation": SKIP,
}

DEFAULT_SOURCES = [
    str(pathlib.Path.home() / "Downloads" /
        "(2024) TC and SE Strategy Series - Session 2 Support_Contrast Words.xlsx"),
    "1IHTug3lVoAIHogqpaD-E3LbRb8-a1q_ghS3wHecgHDM",
]

UA = "gre-vocab/1.0 (personal study project)"


def load(src: str) -> openpyxl.Workbook | None:
    """A local path, or a Google Sheets id/URL fetched as xlsx."""
    p = pathlib.Path(src)
    if p.exists():
        return openpyxl.load_workbook(p, data_only=True)
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", src)
    sid = m.group(1) if m else (src if re.fullmatch(r"[A-Za-z0-9_-]{30,}", src) else None)
    if not sid:
        print(f"  not a file or a sheet id: {src}")
        return None
    url = f"https://docs.google.com/spreadsheets/d/{sid}/export?format=xlsx"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as f:
            return openpyxl.load_workbook(io.BytesIO(f.read()), data_only=True)
    except Exception as e:                                   # noqa: BLE001
        print(f"  could not fetch {sid}: {e}")
        return None


def clean(v) -> str:
    return re.sub(r"\s+", " ", str(v)).strip() if v is not None else ""


# Each sheet labels its own columns, and not always with the sheet's name, so
# "Phrase | Type | Example Sentence" sailed through as a phrase of type "Type".
HEADERS = {"phrase", "phrases", "word", "words", "type", "example sentence",
           "example sentences", "support punctuation"}


def is_header(phrase: str, row, sheet_key: str) -> bool:
    low = phrase.lower()
    if low == sheet_key or low in HEADERS:
        return True
    return any(clean(c).lower() in HEADERS for c in row[1:3])


def main() -> int:
    sources = sys.argv[1:] or DEFAULT_SOURCES
    rows: list[dict] = []
    seen: dict[str, int] = {}          # lowercased phrase -> index in rows
    skipped_sheets: list[str] = []

    for src in sources:
        print(f"{src[:70]}")
        wb = load(src)
        if not wb:
            continue
        for name in wb.sheetnames:
            key = name.strip().lower()
            if key not in SHEETS:
                skipped_sheets.append(f"{name} (unrecognised)")
                continue
            kind = SHEETS[key]
            if kind is SKIP:
                skipped_sheets.append(f"{name} (excluded)")
                continue
            added = 0
            for r in wb[name].iter_rows(values_only=True):
                phrase = clean(r[0] if r else "")
                if not phrase or is_header(phrase, r, key):
                    continue
                if kind is None:
                    t, sentence = clean(r[1] if len(r) > 1 else ""), clean(r[2] if len(r) > 2 else "")
                else:
                    t, sentence = kind, clean(r[1] if len(r) > 1 else "")
                if not t:
                    continue
                # A row of instructions rather than a phrase.
                if len(phrase.split()) > 8 and not sentence:
                    continue
                low = phrase.lower()
                if low in seen:
                    # keep whichever entry actually carries an example
                    if sentence and not rows[seen[low]]["s"]:
                        rows[seen[low]]["s"] = sentence
                    continue
                seen[low] = len(rows)
                rows.append({"p": phrase, "t": t, "s": sentence})
                added += 1
            print(f"  {name}: +{added}")

    rows.sort(key=lambda x: (x["t"], x["p"].lower()))
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")

    kinds: dict[str, int] = {}
    for x in rows:
        kinds[x["t"]] = kinds.get(x["t"], 0) + 1
    print(f"\n{len(rows)} phrases -> {OUT}")
    for k, n in sorted(kinds.items()):
        print(f"  {k}: {n}")
    missing = [x["p"] for x in rows if not x["s"]]
    if missing:
        print(f"  {len(missing)} without an example: {missing[:6]}")
    if skipped_sheets:
        print("  sheets not used: " + ", ".join(sorted(set(skipped_sheets))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
