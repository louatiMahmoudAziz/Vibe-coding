"""Background evaluation worker.

Uploads are queued and evaluated one at a time in an isolated subprocess
(`python -m traffic_sim.cli evaluate <file> --json`), so a hanging or
crashing submission can never take the web server down. Results land in
the database; the leaderboard pages poll and update live.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional, Sequence

from . import db

# Policy budget is 10 s per run and a full evaluation is 15 runs; leave
# generous headroom for interpreter startup and slow shared hosts.
SUBPROCESS_TIMEOUT_S = 240


class Evaluator(threading.Thread):
    def __init__(
        self,
        db_path: Path,
        repo_root: Path,
        seeds: Optional[Sequence[int]] = None,
    ):
        super().__init__(name="evaluator", daemon=True)
        self.db_path = Path(db_path)
        self.repo_root = Path(repo_root)
        self.seeds = tuple(seeds) if seeds else None
        self._queue: "queue.Queue[Optional[int]]" = queue.Queue()

    # -- producer side ----------------------------------------------------

    def submit(self, submission_id: int) -> None:
        self._queue.put(submission_id)

    def requeue_unfinished(self) -> int:
        """Re-enqueue submissions interrupted by a restart. Returns count."""
        pending = db.unfinished_submission_ids(self.db_path)
        for submission_id in pending:
            db.set_submission_status(self.db_path, submission_id, "pending")
            self._queue.put(submission_id)
        return len(pending)

    def stop(self) -> None:
        self._queue.put(None)

    @property
    def backlog(self) -> int:
        return self._queue.qsize()

    # -- worker side -------------------------------------------------------

    def run(self) -> None:
        while True:
            submission_id = self._queue.get()
            if submission_id is None:
                return
            try:
                self._evaluate(submission_id)
            except Exception as exc:  # noqa: BLE001 - keep the worker alive
                db.finish_submission(
                    self.db_path,
                    submission_id,
                    total_score=None,
                    mean_avg_wait=None,
                    detail=None,
                    error=f"internal evaluator error: {exc}",
                )

    def _evaluate(self, submission_id: int) -> None:
        record = db.submission(self.db_path, submission_id)
        if record is None or not record["code_path"]:
            return
        db.set_submission_status(self.db_path, submission_id, "evaluating")

        command = [
            sys.executable,
            "-m",
            "traffic_sim.cli",
            "evaluate",
            record["code_path"],
            "--json",
        ]
        if self.seeds:
            command += ["--seeds", ",".join(map(str, self.seeds))]

        # Score against the act the submission was made in, not whatever act
        # the room has since advanced to -- otherwise a late-finishing Act 1
        # evaluation would be judged by Act 2's requirements.
        act = record["act"] if "act" in record.keys() else None
        if act:
            command += ["--act", act]

        try:
            completed = subprocess.run(
                command,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            db.finish_submission(
                self.db_path,
                submission_id,
                None,
                None,
                None,
                error=f"evaluation timed out after {SUBPROCESS_TIMEOUT_S}s",
            )
            return

        detail = None
        try:
            detail = json.loads(completed.stdout)
        except (json.JSONDecodeError, ValueError):
            pass

        if detail is None:
            stderr_tail = (completed.stderr or "").strip().splitlines()[-3:]
            db.finish_submission(
                self.db_path,
                submission_id,
                None,
                None,
                None,
                error="evaluator produced no result: " + (" | ".join(stderr_tail) or "unknown error"),
            )
            return

        if detail.get("load_error"):
            db.finish_submission(
                self.db_path,
                submission_id,
                None,
                None,
                detail,
                error=f"policy failed to load: {detail['load_error']}",
            )
            return

        # Per-run errors (crashes on some scenarios) still yield a score;
        # surface the first error message alongside it.
        run_errors = []
        for scenario in detail.get("scenarios", []):
            for run in scenario.get("runs", []):
                if run.get("error"):
                    run_errors.append(f"{scenario['scenario']}: {run['error']}")
        db.finish_submission(
            self.db_path,
            submission_id,
            total_score=float(detail.get("total_score", 0.0)),
            mean_avg_wait=float(detail.get("mean_avg_wait", 0.0)),
            detail=detail,
            error=None if not run_errors else "partial: " + run_errors[0],
        )
