"""
Drift detector for the documentation.

lint.py checks that generated content still matches its contract. This does the
same for prose: it verifies that the factual claims in docs/ - counts, schema
fields, storage keys, routes, grouping kinds - still match the repository.

Two limitations, stated plainly because a detector whose blind spots are unknown
is worse than none:

  1. It cannot check whether the *reasoning* in the docs is still true. That
     remains a human or agent judgement, and MAINTAINING-DOCS.md says so.
  2. Presence checks are substring matches over the whole file. So it reliably
     catches something NEW being undocumented, but not something being moved out
     of the right table while the word survives elsewhere in the file. Verified
     by negative test: renaming a storage key was caught; renaming one row of the
     schema table was not.

    python docs_check.py          # report drift, exit 1 if any
    python docs_check.py -v       # also list what was verified
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
DOCS = HERE / "docs"

problems: list[str] = []
checked: list[str] = []


def doc(name: str) -> str:
    p = DOCS / name
    return p.read_text(encoding="utf-8") if p.exists() else ""


def want(cond: bool, msg: str, ok: str) -> None:
    (checked if cond else problems).append(ok if cond else msg)


def approx_in(value: int, text: str, label: str, tol: float = 0.02) -> None:
    """Is a number close to `value` mentioned anywhere in the text?

    Docs legitimately round ("~2,010", "roughly 655"), so exact matching would
    produce noise. Anything within tolerance counts.
    """
    nums = [int(n.replace(",", "").replace("_", ""))
            for n in re.findall(r"\b\d[\d,_]*\b", text)]
    hit = any(abs(n - value) <= max(1, value * tol) for n in nums)
    want(hit, f"{label}: {value} is not mentioned in the docs (stale count?)",
         f"{label} = {value}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if not DOCS.exists():
        print("docs/ is missing entirely")
        return 1

    all_docs = "\n".join(doc(p.name) for p in DOCS.glob("*.md"))

    # ---- counts -----------------------------------------------------------
    cards = glob.glob("cards/*.json")
    approx_in(len(cards), all_docs, "cards")

    groups = [json.loads(Path(f).read_text(encoding="utf-8"))
              for f in glob.glob("groups/*/*.json")]
    written = [g for g in groups if g.get("core")]
    approx_in(len(written), all_docs, "written groups")

    bank = [q for f in glob.glob("bank/*.json")
            for q in json.loads(Path(f).read_text(encoding="utf-8"))["questions"]]
    if bank:
        approx_in(len(bank), all_docs, "bank questions")

    words = json.loads(Path("words.json").read_text(encoding="utf-8"))
    approx_in(len(words), all_docs, "words in words.json")

    # ---- grouping kinds ---------------------------------------------------
    kinds = {p.name for p in Path("groups").iterdir() if p.is_dir()} if Path("groups").exists() else set()
    for k in kinds:
        want(k in all_docs, f"grouping kind '{k}' exists but is undocumented",
             f"kind '{k}' documented")

    # ---- card schema ------------------------------------------------------
    try:
        sys.path.insert(0, str(HERE))
        from cardspec import CARD_SCHEMA
        dm = doc("DATA-MODEL.md")
        for f in CARD_SCHEMA["required"]:
            want(f in dm, f"card field '{f}' is not documented in DATA-MODEL.md",
                 f"card field '{f}'")
        documented = set(re.findall(r"`([a-z_]+)`", dm))
        for f in documented & {"memory_image", "image", "scene"}:
            problems.append(f"DATA-MODEL.md mentions '{f}', which was abolished")
    except Exception as e:  # noqa: BLE001
        problems.append(f"could not import CARD_SCHEMA: {e}")

    # ---- app: storage keys and routes -------------------------------------
    app = Path("build_app.py").read_text(encoding="utf-8")
    dm = doc("DATA-MODEL.md")
    for key in sorted(set(re.findall(r'"(gre-vocab-[a-z0-9-]+)"', app))):
        want(key in dm, f"localStorage key '{key}' is used but undocumented",
             f"storage key '{key}'")
    for route in sorted(set(re.findall(r'"(/(?:browse|drill|quiz|groups))"', app))):
        want(route in dm, f"route '{route}' is used but undocumented",
             f"route '{route}'")

    # ---- scripts ----------------------------------------------------------
    for py in sorted(glob.glob("*.py")):
        if py == "docs_check.py":
            continue
        want(py in all_docs, f"script '{py}' is not mentioned anywhere in docs/",
             f"script '{py}'")

    # ---- the docs themselves ----------------------------------------------
    for required in ("README.md", "PHILOSOPHY.md", "ARCHITECTURE.md",
                     "DATA-MODEL.md", "DECISIONS.md", "OPERATIONS.md",
                     "MAINTAINING-DOCS.md"):
        want((DOCS / required).exists(), f"docs/{required} is missing",
             f"docs/{required}")

    # ---- report -----------------------------------------------------------
    if args.verbose:
        for c in checked:
            print(f"  ok    {c}")
    if problems:
        print(f"\n{len(problems)} documentation problem(s):\n")
        for p in problems:
            print(f"  DRIFT  {p}")
        print("\nSee docs/MAINTAINING-DOCS.md for what to update.")
        return 1
    print(f"docs are in step with the repository ({len(checked)} checks passed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
