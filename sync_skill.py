"""
Keep the vendored copy of the gre-word-coach skill in step with the live one.

The live skill at ~/.claude/skills/gre-word-coach is where the card format is
actually tuned - Claude edits it there when you give feedback. This script
copies it into skill/ so the repo carries the exact spec that produced the
cards, and a fresh clone can regenerate them.

Run it before committing whenever the format has changed.

    python sync_skill.py            # live -> repo (the usual direction)
    python sync_skill.py --check    # exit 1 if they differ, for a pre-commit hook
    python sync_skill.py --push     # repo -> live (restore after a fresh clone)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

LIVE = Path.home() / ".claude" / "skills" / "gre-word-coach"
VENDORED = Path(__file__).parent / "skill"

FILES = [Path("SKILL.md"), Path("reference/exemplar-censor.md")]


def copy(src_root: Path, dst_root: Path) -> list[str]:
    changed = []
    for rel in FILES:
        src, dst = src_root / rel, dst_root / rel
        if not src.exists():
            print(f"  missing in source, skipped: {rel}")
            continue
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        changed.append(str(rel))
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report drift, change nothing")
    ap.add_argument("--push", action="store_true", help="copy repo -> live instead")
    args = ap.parse_args()

    if args.check:
        drift = [str(r) for r in FILES
                 if not (VENDORED / r).exists()
                 or not (LIVE / r).exists()
                 or (LIVE / r).read_bytes() != (VENDORED / r).read_bytes()]
        if drift:
            print("skill/ is out of date with the live skill:")
            for d in drift:
                print("   ", d)
            print("run: python sync_skill.py")
            return 1
        print("skill/ is in sync")
        return 0

    src, dst, arrow = (VENDORED, LIVE, "repo -> live") if args.push else (LIVE, VENDORED, "live -> repo")
    if not (src / "SKILL.md").exists():
        print(f"source skill not found at {src}")
        return 2

    changed = copy(src, dst)
    print(f"{arrow}: {'updated ' + ', '.join(changed) if changed else 'already in sync'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
