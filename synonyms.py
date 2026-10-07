#!/usr/bin/env python3
"""Top up each card word's synonyms from a dictionary, into synonyms.json.

The app's own meaning and intensity clusters already cover 924 of 1112 words
and are better than any dictionary for GRE purposes, because they were written
to separate near-synonyms rather than pile them up. This fills the gap for the
rest and widens the list where a cluster is thin.

Source: Datamuse (api.datamuse.com), which needs no key and no registration.

    python synonyms.py              # Datamuse only
    MW_KEY=xxxx python synonyms.py  # also merge Merriam-Webster's thesaurus

WHY NOT SCRAPE MERRIAM-WEBSTER
------------------------------
merriam-webster.com returns 403 to anything that is not a real browser, for
both /dictionary and /thesaurus. Their robots.txt does not forbid those paths,
but the server refuses, so the supported route is their API at
dictionaryapi.com, which needs a free key. Set MW_KEY to use it; without one
this still works, just from Datamuse alone.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).parent
CARDS = HERE / "cards"
OUT = HERE / "synonyms.json"

UA = "gre-vocab/1.0 (personal study project)"
PER_WORD = 8
MIN_SCORE = 2000          # Datamuse scores; below this the matches get loose

SUFFIX = ("ations", "ation", "ingly", "ously", "ities", "ness", "ment", "able",
          "ible", "ance", "ence", "ing", "ion", "ive", "ity", "ous", "ate",
          "ly", "ed", "es", "s")


def stem(w: str) -> str:
    w = re.sub(r"[^a-z]", "", w.lower())
    for suf in SUFFIX:
        if len(w) - len(suf) >= 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def get(url: str) -> list | dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as f:
        return json.loads(f.read().decode("utf-8", "replace"))


def datamuse(word: str) -> list[str]:
    url = ("https://api.datamuse.com/words?rel_syn="
           + urllib.parse.quote(word) + "&max=20")
    try:
        rows = get(url)
    except Exception:                                    # noqa: BLE001
        return []
    out = []
    for r in rows:
        w = r.get("word", "")
        if r.get("score", 0) < MIN_SCORE:
            continue
        # single words only: a definition fragment is not a synonym
        if not re.fullmatch(r"[a-z]+(?:-[a-z]+)?", w):
            continue
        if len(w) < 3 or stem(w) == stem(word):          # "abounding" for "abound"
            continue
        out.append(w)
    return out


def merriam(word: str, key: str) -> list[str]:
    url = ("https://www.dictionaryapi.com/api/v3/references/thesaurus/json/"
           + urllib.parse.quote(word) + "?key=" + key)
    try:
        rows = get(url)
    except Exception:                                    # noqa: BLE001
        return []
    out = []
    for entry in rows:
        if not isinstance(entry, dict):                  # a miss returns suggestions
            continue
        for group in (entry.get("meta") or {}).get("syns") or []:
            for w in group:
                if re.fullmatch(r"[a-z]+(?:-[a-z]+)?", w) and stem(w) != stem(word):
                    out.append(w)
    return out


def main() -> int:
    words = [json.loads(p.read_text(encoding="utf-8"))["word"]
             for p in sorted(CARDS.glob("*.json"))]
    key = os.environ.get("MW_KEY", "").strip()
    print(f"{len(words)} words · Datamuse" + (" + Merriam-Webster" if key else ""))

    out: dict[str, list[str]] = {}
    if OUT.exists():                                     # resumable
        out = json.loads(OUT.read_text(encoding="utf-8"))

    done = 0
    for w in words:
        if w in out:
            continue
        syns = datamuse(w)
        if key:
            for s in merriam(w, key):
                if s not in syns:
                    syns.append(s)
        if syns:
            out[w] = syns[:PER_WORD]
        done += 1
        if done % 100 == 0:
            print(f"  {done} fetched, {len(out)} with synonyms", flush=True)
            OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
        time.sleep(0.06)                                 # be polite

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    hit = len(out)
    print(f"{hit}/{len(words)} words got synonyms ({100*hit/len(words):.0f}%) -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
