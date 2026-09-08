#!/usr/bin/env python3
"""Match every card word to iswearenglish videos.

The channel (19,786 videos) is the reason this project exists - the card format
was calibrated against how that channel explains a word. Linking each card to
the actual video closes the loop.

Two stages, cached separately so re-matching never re-crawls:

    python videos.py --crawl     videos/catalogue.json   (~10 min, 660 pages)
    python videos.py             videos.json             (instant)

WHY THE TITLE PARSING LOOKS LIKE THIS
-------------------------------------
Titles on that channel follow one grammar:

    EMOJI Word Meaning - Word Examples - Define Word - Word In A Sentence - Category

so the subject is whatever survives removing boilerplate TOKENS. The obvious
approach - dropping whole segments containing "Meaning" - throws away the very
word being looked for, and scores 25% instead of 91%.

WHY MATCHING IS EXACT-FORM ONLY
-------------------------------
Allowing morphological variants ("commence" via "Comment") added 20 words and
about half were wrong: commence -> a video on Spanish elections, universal ->
"University", passable -> "Pass". Precision over recall, as everywhere else
here. A variant still matches when the video names both forms, which is how
"aberrant" reaches the Aberration video - "Aberrant" is in that title too.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.request

HERE = pathlib.Path(__file__).parent
CARDS = HERE / "cards"
CATALOGUE = HERE / "videos" / "catalogue.json"
OUT = HERE / "videos.json"

CHANNEL = "UC6UdDGN__Ct3mYSu9H5M6Hw"
HANDLE = "iswearenglish"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Tokens that describe a video rather than name its subject.
FILLER = set("""meaning meanings means meant definition definitions define defines
defined defining example examples explained explain explains sentence sentences
pronunciation pronounce pronounced spelling synonym synonyms antonym antonyms
difference differences between vs versus what which who how why when where does do is
are was a an the in on at to of for with and or not use used using word words this
that it its from""".split())

# Segments that are only a category label. Individual tokens are dropped too, so
# "Essential Adjectives" trailing a title cannot become a subject.
CATEGORY = set("""esl gre ielts toefl sat cae cpe c1 c2 b2 3500 formal informal
literary academic advanced english vocabulary vocab learn lesson lessons daily common
useful phrasal verb verbs idiom idioms business exam exams test native speaker
speakers british american grammar writing speaking reading listening tips trick tricks
study adjective adjectives adverb adverbs noun nouns describing describe person people
character characters explanation essential everyday powerful important must know top
best list part series phrase phrases expression expressions emotion emotions feeling
feelings personality negative positive elegant precise uncommon rare
difficult easy quick short full complete guide master improve boost upgrade smart
fluent fluency confident intermediate beginner upper lower level pack set
collection""".split())

SUFFIX = ("ations", "ation", "ements", "ement", "iously", "ously", "ingly", "ities",
          "ility", "ently", "antly", "ances", "ences", "ance", "ence", "ancy", "ency",
          "ions", "ion", "ive", "ing", "ors", "ers", "est", "ies", "ied", "ely",
          "ness", "ment", "able", "ible", "ent", "ant", "ity", "ous", "ate", "ally",
          "ly", "al", "ed", "es", "or", "er", "s")

WORD_RE = re.compile(r"[A-Za-zÀ-ɏ][A-Za-zÀ-ɏ'’\-]*")

# The channel also does literature. "Bright Star Would I Were Steadfast Thou Art
# - John Keats - Analysis" is not a video about the word "steadfast", and every
# proper noun in such a title parses as a subject.
REJECT = re.compile(r"\b(analysis|analyse|analyze|summary|summaries|poem|poetry|"
                    r"sonnet|stanza|novel|chapter|act\s+\w+\s+scene)\b", re.I)


def stem(w: str) -> str:
    w = unicodedata.normalize("NFKD", w.lower())     # naive and naïve are one word
    w = re.sub(r"[^a-z]", "", w)
    for suf in SUFFIX:
        if len(w) - len(suf) >= 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def subjects(title: str) -> list[str]:
    """The words a video is actually about, in the order they first appear."""
    t = re.sub(r"^[^\w]+", "", title)
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)
    seen: set[str] = set()
    out: list[str] = []
    for seg in re.split(r"\s*[-–—|:,/]\s*|\s{2,}", t):
        keep = [x for x in WORD_RE.findall(seg) if x.lower() not in FILLER]
        if not keep or all(x.lower() in CATEGORY for x in keep):
            continue
        for x in keep:
            if x.lower() in CATEGORY or len(x) < 3:
                continue
            if x.lower() not in seen:
                seen.add(x.lower())
                out.append(x)
    return out


def classify(subs: list[str]) -> str:
    """One word or several?

    Subjects sharing a long stem prefix are inflections of a single word
    (evanescent / evanesce / evanescence). Genuinely different words diverge
    early (censure / censor / censer / sensor).
    """
    stems = sorted({stem(s) for s in subs})
    if len(stems) == 1:
        return "dedicated"
    a, b = stems[0], stems[-1]
    lcp = 0
    while lcp < min(len(a), len(b)) and a[lcp] == b[lcp]:
        lcp += 1
    return "dedicated" if lcp >= 4 else "group"


# ---------------------------------------------------------------- crawling

def _fetch(url: str, data: bytes | None = None) -> str:
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if data:
        h["Content-Type"] = "application/json"
    raw = urllib.request.urlopen(
        urllib.request.Request(url, data=data, headers=h), timeout=60).read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def _lockups(node, out: dict) -> None:
    """Videos arrive as lockupViewModel; YouTube retired videoRenderer here."""
    if isinstance(node, dict):
        lv = node.get("lockupViewModel")
        if isinstance(lv, dict):
            vid = lv.get("contentId")
            t = (lv.get("metadata", {}).get("lockupMetadataViewModel", {})
                   .get("title", {}).get("content"))
            if vid and t:
                out[vid] = t
        for v in node.values():
            _lockups(v, out)
    elif isinstance(node, list):
        for v in node:
            _lockups(v, out)


def _tokens(node, out: list) -> None:
    if isinstance(node, dict):
        c = node.get("continuationCommand")
        if isinstance(c, dict) and c.get("token"):
            out.append(c["token"])
        for v in node.values():
            _tokens(v, out)
    elif isinstance(node, list):
        for v in node:
            _tokens(v, out)


def crawl() -> dict[str, str]:
    html = _fetch(f"https://www.youtube.com/channel/{CHANNEL}/videos")
    key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html).group(1)
    ver = re.search(r'"clientVersion":"([\d.]+)"', html).group(1)
    data = json.loads(re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S).group(1))

    vids: dict[str, str] = {}
    _lockups(data, vids)
    tk: list[str] = []
    _tokens(data, tk)
    tok = tk[0] if tk else None

    page = 1
    while tok:
        page += 1
        body = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": ver}},
                           "continuation": tok}).encode()
        try:
            nxt = json.loads(_fetch(f"https://www.youtube.com/youtubei/v1/browse?key={key}", body))
        except Exception as e:                                   # noqa: BLE001
            print(f"  stopped at page {page}: {e}")
            break
        before = len(vids)
        _lockups(nxt, vids)
        tk = []
        _tokens(nxt, tk)
        tok = tk[0] if tk else None
        if len(vids) == before:
            break
        if page % 50 == 0:
            print(f"  page {page}: {len(vids)} videos")
        time.sleep(0.4)                                          # be gentle
    return vids


# ---------------------------------------------------------------- matching

def build_index(catalogue: dict[str, str]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = collections.defaultdict(list)
    for vid, title in catalogue.items():
        if REJECT.search(title):
            continue
        subs = subjects(title)
        # A cap catches genuine parse failures, but it has to clear the channel's
        # big synonym round-ups - "Moan Groan Bellyache Grumble Grouse Grouch
        # Growl Grunt Gripe Grizzle" is ten subjects and exactly what we want.
        if not subs or len(subs) > 14:
            continue
        kind = classify(subs)
        for s in subs:
            index[stem(s)].append({"id": vid, "kind": kind, "subjects": subs,
                                   "title": title, "matched": s})
    return index


def pick(word: str, index) -> list[dict]:
    """At most one dedicated and one group video, best first."""
    # Four card entries are phrases ("ad hoc", "stem from"). A title splits them
    # into separate tokens, so match the run of consecutive subjects too.
    parts = [p for p in re.split(r"[\s\-]+", word.lower()) if p]
    if len(parts) > 1:
        phrase = re.compile(r"\b" + r"[\s\-]+".join(map(re.escape, parts)) + r"\b", re.I)
        hits = [h for h in index.get(stem(parts[0]), []) if phrase.search(h["title"])]
    else:
        hits = [h for h in index.get(stem(word), [])
                if any(s.lower() == word.lower() for s in h["subjects"])]

    def rank(h):
        return (len(h["subjects"]), len(h["title"]))

    ded = sorted([h for h in hits if h["kind"] == "dedicated"], key=rank)
    grp = sorted([h for h in hits if h["kind"] == "group"], key=rank)
    out = []
    for h in ([ded[0]] if ded else []) + ([grp[0]] if grp else []):
        out.append({"id": h["id"], "kind": h["kind"], "subjects": h["subjects"]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crawl", action="store_true",
                    help="re-fetch the channel catalogue (slow) before matching")
    args = ap.parse_args()

    if args.crawl or not CATALOGUE.exists():
        print(f"crawling {HANDLE}...")
        cat = crawl()
        CATALOGUE.parent.mkdir(exist_ok=True)
        CATALOGUE.write_text(json.dumps(cat, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"  {len(cat)} videos -> {CATALOGUE}")
    cat = json.loads(CATALOGUE.read_text(encoding="utf-8"))

    files = sorted(CARDS.glob("*.json"))
    if not files:
        print(f"no cards in {CARDS}")
        return 1
    words = [json.loads(f.read_text(encoding="utf-8"))["word"] for f in files]

    index = build_index(cat)
    out = {}
    for w in words:
        hits = pick(w, index)
        if hits:
            out[w] = hits

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    both = sum(1 for v in out.values() if len(v) == 2)
    seen = len({h["id"] for v in out.values() for h in v})
    print(f"{len(cat)} videos in catalogue")
    print(f"{len(out)}/{len(words)} words matched ({100 * len(out) / len(words):.0f}%), "
          f"{both} with both a dedicated and a group video, {seen} distinct videos")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
