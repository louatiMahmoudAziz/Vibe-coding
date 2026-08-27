"""SQLite storage for participants and their submissions.

Connections are opened per operation (cheap at workshop scale) with WAL
mode, so the HTTP threads and the evaluation worker can share the file
safely.
"""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_participants_name
    ON participants (name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participants (id),
    created_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',   -- pending|evaluating|scored|error
    total_score REAL,
    mean_avg_wait REAL,
    detail_json TEXT,
    error TEXT,
    code_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_submissions_participant
    ON submissions (participant_id, created_at);
"""

NAME_RE = re.compile(r"^[\w .\-'()&!]{2,40}$", re.UNICODE)


class SignupError(ValueError):
    pass


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(db_path: Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def normalize_name(raw: str) -> str:
    name = " ".join(raw.split())
    if not NAME_RE.match(name):
        raise SignupError(
            "Name must be 2-40 characters: letters, digits, spaces and . - ' ( ) & !"
        )
    return name


def create_participant(db_path: Path, raw_name: str) -> Dict:
    name = normalize_name(raw_name)
    token = secrets.token_urlsafe(16)
    with connect(db_path) as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO participants (name, token, created_at) VALUES (?, ?, ?)",
                (name, token, time.time()),
            )
        except sqlite3.IntegrityError:
            raise SignupError(f"The name {name!r} is already taken.") from None
        return {"id": cursor.lastrowid, "name": name, "token": token}


def participant_by_token(db_path: Path, token: str) -> Optional[Dict]:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM participants WHERE token = ?", (token,)
        ).fetchone()
        return dict(row) if row else None


def create_submission(db_path: Path, participant_id: int) -> int:
    with connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO submissions (participant_id, created_at) VALUES (?, ?)",
            (participant_id, time.time()),
        )
        return cursor.lastrowid


def set_submission_code_path(db_path: Path, submission_id: int, code_path: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE submissions SET code_path = ? WHERE id = ?",
            (code_path, submission_id),
        )


def set_submission_status(db_path: Path, submission_id: int, status: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE submissions SET status = ? WHERE id = ?", (status, submission_id)
        )


def finish_submission(
    db_path: Path,
    submission_id: int,
    total_score: Optional[float],
    mean_avg_wait: Optional[float],
    detail: Optional[Dict],
    error: Optional[str],
) -> None:
    # A submission with a score counts as scored even if some runs errored
    # (the note is surfaced next to the score); no score at all is an error.
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE submissions SET status = ?, total_score = ?, mean_avg_wait = ?, "
            "detail_json = ?, error = ? WHERE id = ?",
            (
                "scored" if total_score is not None else "error",
                total_score,
                mean_avg_wait,
                json.dumps(detail) if detail is not None else None,
                error,
                submission_id,
            ),
        )


def submission(db_path: Path, submission_id: int) -> Optional[Dict]:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        return dict(row) if row else None


def submissions_for(db_path: Path, participant_id: int) -> List[Dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE participant_id = ? "
            "ORDER BY created_at DESC",
            (participant_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def last_submission_at(db_path: Path, participant_id: int) -> float:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT MAX(created_at) AS latest FROM submissions WHERE participant_id = ?",
            (participant_id,),
        ).fetchone()
        return row["latest"] or 0.0


def unfinished_submission_ids(db_path: Path) -> List[int]:
    """Submissions interrupted by a server restart, to be re-queued."""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM submissions WHERE status IN ('pending', 'evaluating') "
            "ORDER BY created_at"
        ).fetchall()
        return [row["id"] for row in rows]


def leaderboard(db_path: Path) -> List[Dict]:
    """One entry per participant: best scored submission plus activity info."""
    with connect(db_path) as conn:
        participants = conn.execute(
            "SELECT * FROM participants ORDER BY created_at"
        ).fetchall()
        entries = []
        for person in participants:
            subs = conn.execute(
                "SELECT * FROM submissions WHERE participant_id = ? "
                "ORDER BY created_at",
                (person["id"],),
            ).fetchall()
            scored = [s for s in subs if s["status"] == "scored"]
            best = max(scored, key=lambda s: s["total_score"]) if scored else None
            latest = subs[-1] if subs else None
            entries.append(
                {
                    "name": person["name"],
                    "attempts": len(subs),
                    "best_score": best["total_score"] if best else None,
                    "best_at": best["created_at"] if best else None,
                    "best_detail": json.loads(best["detail_json"])
                    if best and best["detail_json"]
                    else None,
                    "best_mean_avg_wait": best["mean_avg_wait"] if best else None,
                    "latest_status": latest["status"] if latest else None,
                    "latest_error": latest["error"] if latest else None,
                    "last_activity": latest["created_at"] if latest else None,
                }
            )

    def sort_key(entry):
        has_score = entry["best_score"] is not None
        return (
            0 if has_score else 1,
            -(entry["best_score"] or 0.0),
            entry["best_at"] or float("inf"),  # earlier achiever wins ties
            entry["name"].lower(),
        )

    return sorted(entries, key=sort_key)


def all_participants_with_best(db_path: Path) -> List[Dict]:
    """For the finals export: participant name + best submission code path."""
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT p.name AS name, s.code_path AS code_path,
                   s.total_score AS total_score, s.created_at AS created_at
            FROM participants p
            JOIN submissions s ON s.participant_id = p.id
            WHERE s.status = 'scored'
            """
        ).fetchall()
    best: Dict[str, Dict] = {}
    for row in rows:
        entry = dict(row)
        current = best.get(entry["name"])
        if current is None or entry["total_score"] > current["total_score"]:
            best[entry["name"]] = entry
    return sorted(best.values(), key=lambda e: -e["total_score"])
