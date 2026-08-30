#!/usr/bin/env python3
"""Wipe the board and rebuild it from known controllers, for dry runs.

Why this exists: asking an LLM the same question twice does not give you the
same controller twice, so "paste the persona prompts again" is not a
reproducible test. These files ARE the controllers those prompts produce, so
seeding from them lets you rehearse the whole arc -- and check that the
leaderboard reorders the way it should when you advance the act -- without
spending AI budget or depending on luck.

    python scripts/seed_personas.py --db /home/server_data --reset
    python scripts/seed_personas.py --db /home/server_data --act act2
    python scripts/seed_personas.py --db /home/server_data --act deployment

Each run re-evaluates every persona against the act you name and prints the
board as participants would see it.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from traffic_sim.runner import evaluate_submission  # noqa: E402
from webboard import db  # noqa: E402

# Persona -> the controller that persona's prompt actually produces.
PERSONAS = [
    ("Non-programmer",      "solutions/personas/p1_non_programmer.py"),
    ("First-year CS",       "solutions/personas/p2_first_year_cs.py"),
    ("Algorithms student",  "solutions/personas/p3_algorithms_student.py"),
    ("Half-fixer",          "solutions/personas/p4_half_fixer.py"),
    ("Experienced dev",     "solutions/personas/p5_experienced_dev.py"),
    ("Vibe-coding native",  "solutions/personas/p6_vibe_native.py"),
    ("The winner",          "solutions/act2_ceiling.py"),
    ("Fixed timer",         "submissions/team_fixed_timer/policy.py"),
]

PASSWORD = "personas"


def reset(db_path: Path) -> None:
    """Delete every participant and submission. The board only, never the code."""
    with db.connect(db_path) as conn:
        try:
            subs = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
            people = conn.execute("SELECT COUNT(*) FROM participants").fetchone()[0]
        except sqlite3.OperationalError:
            subs = people = 0
        conn.execute("DELETE FROM submissions")
        conn.execute("DELETE FROM participants")
        try:  # only present once an AUTOINCREMENT row has existed
            conn.execute("DELETE FROM sqlite_sequence WHERE name IN "
                         "('submissions','participants')")
        except sqlite3.OperationalError:
            pass
    print(f"  wiped {people} participant(s) and {subs} submission(s)")


def seed(db_path: Path, act: str) -> None:
    db.set_current_act(db_path, act)
    store = db_path.parent / "personas"
    store.mkdir(parents=True, exist_ok=True)

    for name, rel in PERSONAS:
        source = REPO / rel
        if not source.exists():
            print(f"  !! missing {rel}, skipping {name}")
            continue
        try:
            person = db.create_participant(db_path, name, PASSWORD)
        except db.SignupError:                     # already seeded
            person = db.authenticate(db_path, name, PASSWORD)
        code_path = store / f"{person['id']}_{source.name}"
        shutil.copyfile(source, code_path)

        sub = db.create_submission(db_path, person["id"], act=act)
        db.set_submission_code_path(db_path, sub, str(code_path))
        result = evaluate_submission(code_path, act=act)
        detail = result.to_dict()
        db.finish_submission(
            db_path, sub,
            total_score=result.total,
            mean_avg_wait=result.mean_avg_wait,
            detail=detail,
            error=None,
        )
        print(f"  {name:<22} {'PASS' if result.passed_all else 'fail':<5} "
              f"avg {result.mean_avg_wait:5.1f}s  worst {result.worst_wait:4d}s")


def show(db_path: Path, act: str) -> None:
    print(f"\n  BOARD as participants see it ({act})")
    print(f"  {'#':<3}{'participant':<22}{'requirements':<34}{'wait':>7}")
    print("  " + "-" * 64)
    for i, entry in enumerate(db.leaderboard(db_path), 1):
        verdict = "all met" if entry["best_passed"] else "missed a requirement"
        wait = entry["best_rank_wait"]
        print(f"  {i:<3}{entry['name']:<22}{verdict:<34}"
              f"{('-' if wait is None else f'{wait:.1f}s'):>7}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="data", help="server data directory")
    ap.add_argument("--act", default="act1", choices=list(db.ACTS))
    ap.add_argument("--reset", action="store_true",
                    help="delete all accounts and submissions first")
    args = ap.parse_args()

    data_dir = Path(args.db)
    data_dir.mkdir(parents=True, exist_ok=True)
    # Match the server: the data directory holds board.sqlite3 beside it.
    db_path = data_dir / "board.sqlite3"
    db.init(db_path)

    if args.reset:
        print("resetting board")
        reset(db_path)
    print(f"seeding {len(PERSONAS)} personas for {args.act}")
    seed(db_path, args.act)
    show(db_path, args.act)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
