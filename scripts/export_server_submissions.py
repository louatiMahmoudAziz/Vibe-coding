#!/usr/bin/env python3
"""Export each participant's best server upload into a submissions/ layout,
so the finals can be re-scored on hidden seeds with the standard tooling.

Usage:
    python scripts/export_server_submissions.py --data server_data --out finals_submissions
    python scripts/build_leaderboard.py --submissions finals_submissions \
        --seeds 9241,7717,3583 --out results_final
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from webboard import db  # noqa: E402


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "participant"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="server_data")
    parser.add_argument("--out", default="finals_submissions")
    args = parser.parse_args()

    db_path = Path(args.data) / "board.sqlite3"
    if not db_path.exists():
        print(f"no database at {db_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    entries = db.all_participants_with_best(db_path)
    if not entries:
        print("no scored submissions to export", file=sys.stderr)
        return 1

    used = set()
    for entry in entries:
        slug = slugify(entry["name"])
        while slug in used:
            slug += "_x"
        used.add(slug)
        team_dir = out_dir / slug
        team_dir.mkdir(exist_ok=True)
        code = Path(entry["code_path"]).read_text()
        # Force the leaderboard display name to the signup name, overriding
        # any TEAM_NAME the uploaded code may set.
        code += f"\n\nTEAM_NAME = {entry['name']!r}  # set by export\n"
        (team_dir / "policy.py").write_text(code)
        print(f"exported {entry['name']!r} (public best {entry['total_score']:.2f}) -> {team_dir}")

    print(f"\n{len(entries)} participant(s) exported. Score the finals with:")
    print(
        f"  python scripts/build_leaderboard.py --submissions {out_dir} "
        "--seeds <hidden> --out results_final"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
