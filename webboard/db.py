"""SQLite storage for participants and their submissions.

Connections are opened per operation (cheap at workshop scale) with WAL
mode, so the HTTP threads and the evaluation worker can share the file
safely.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
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
    password_hash TEXT,
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
    code_path TEXT,
    act TEXT NOT NULL DEFAULT 'act1'
);

CREATE TABLE IF NOT EXISTS board_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_submissions_participant
    ON submissions (participant_id, created_at);
"""

NAME_RE = re.compile(r"^[\w .\-'()&!]{2,40}$", re.UNICODE)


class SignupError(ValueError):
    pass


def _journal_mode() -> str:
    """WAL locally; DELETE on App Service.

    App Service mounts /home over SMB. SQLite's WAL mode needs to mmap a
    shared-memory (-shm) file, which network filesystems do not support,
    and SMB's advisory locking is unreliable. DELETE journaling is the
    mode SQLite supports on network storage. Override with
    VCC_SQLITE_JOURNAL if you know better than this heuristic.
    """
    explicit = os.environ.get("VCC_SQLITE_JOURNAL", "").strip().upper()
    if explicit:
        return explicit
    if os.environ.get("WEBSITE_INSTANCE_ID"):   # set by App Service
        return "DELETE"
    return "WAL"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA journal_mode={_journal_mode()}")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(db_path: Path) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        # A database created before acts existed has no act column.
        columns = {row[1] for row in conn.execute('PRAGMA table_info(submissions)')}
        if "act" not in columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN act TEXT NOT NULL DEFAULT 'act1'")
        # Migration for databases created before accounts had passwords.
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(participants)")
        }
        if "password_hash" not in columns:
            conn.execute("ALTER TABLE participants ADD COLUMN password_hash TEXT")


# -- passwords ---------------------------------------------------------------

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    try:
        _algo, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, AttributeError):
        return False


def normalize_password(raw: str) -> str:
    if not 4 <= len(raw) <= 64:
        raise SignupError("Password must be 4-64 characters.")
    return raw


def normalize_name(raw: str) -> str:
    name = " ".join(raw.split())
    if not NAME_RE.match(name):
        raise SignupError(
            "Name must be 2-40 characters: letters, digits, spaces and . - ' ( ) & !"
        )
    return name


def create_participant(db_path: Path, raw_name: str, raw_password: str) -> Dict:
    name = normalize_name(raw_name)
    password_hash = hash_password(normalize_password(raw_password))
    token = secrets.token_urlsafe(16)
    with connect(db_path) as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO participants (name, token, password_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (name, token, password_hash, time.time()),
            )
        except sqlite3.IntegrityError:
            raise SignupError(f"The name {name!r} is already taken.") from None
        return {"id": cursor.lastrowid, "name": name, "token": token}


def authenticate(db_path: Path, raw_name: str, password: str) -> Optional[Dict]:
    """Return the participant if name + password match, else None."""
    name = " ".join(raw_name.split())
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM participants WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
    if row is None or not row["password_hash"]:
        return None
    if not check_password(password, row["password_hash"]):
        return None
    return dict(row)


def participant_by_token(db_path: Path, token: str) -> Optional[Dict]:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM participants WHERE token = ?", (token,)
        ).fetchone()
        return dict(row) if row else None



# --------------------------------------------------------------------------- #
# Which act the room is in
#
# One value, shared by everybody. The organiser advances it and every
# participant moves at the same moment -- individual unlocking would let the
# fast third run ahead and lose the collective reveal, which is most of what
# the second act is for.
# --------------------------------------------------------------------------- #

ACTS = ("act1", "act2", "deployment")


def current_act(db_path: Path) -> str:
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM board_state WHERE key = 'act'"
        ).fetchone()
    act = row["value"] if row else "act1"
    return act if act in ACTS else "act1"


def set_current_act(db_path: Path, act: str) -> str:
    if act not in ACTS:
        raise ValueError(f"unknown act {act!r}")
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO board_state (key, value) VALUES ('act', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (act,),
        )
    return act


def submissions_in_act(db_path: Path, participant_id: int, act: str) -> List[Dict]:
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE participant_id = ? AND act = ? "
            "ORDER BY created_at DESC",
            (participant_id, act),
        ).fetchall()
        return [dict(row) for row in rows]


def create_submission(db_path: Path, participant_id: int, act: str = "act1") -> int:
    with connect(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO submissions (participant_id, created_at, act) "
            "VALUES (?, ?, ?)",
            (participant_id, time.time(), act),
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
