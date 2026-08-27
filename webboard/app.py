"""HTTP server: signup, personal upload pages, JSON API, live leaderboard."""

from __future__ import annotations

import json
import time
from email.parser import BytesParser
from email.policy import default as _email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional, Sequence
from urllib.parse import parse_qs, quote, urlparse

from traffic_sim.scenarios import DEFAULT_SEEDS, SCENARIOS

from . import db, pages
from .evaluator import Evaluator

MAX_UPLOAD_BYTES = 200_000
UPLOAD_COOLDOWN_S = 15


def parse_form(content_type: str, body: bytes) -> Dict[str, bytes]:
    """Parse urlencoded or multipart form bodies with the stdlib only."""
    fields: Dict[str, bytes] = {}
    main_type = (content_type or "").split(";")[0].strip().lower()
    if main_type == "application/x-www-form-urlencoded":
        for key, values in parse_qs(body.decode("utf-8", "replace")).items():
            fields[key] = values[0].encode("utf-8")
    elif main_type == "multipart/form-data":
        prefix = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n"
        message = BytesParser(policy=_email_policy).parsebytes(
            prefix.encode("utf-8") + body
        )
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            if name:
                fields[str(name)] = part.get_payload(decode=True) or b""
    return fields


class BoardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data_dir: Path, seeds: Optional[Sequence[int]] = None):
        super().__init__(address, BoardHandler)
        self.data_dir = Path(data_dir)
        self.uploads_dir = self.data_dir / "uploads"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "board.sqlite3"
        self.seeds = tuple(seeds) if seeds else DEFAULT_SEEDS
        db.init(self.db_path)
        repo_root = Path(__file__).resolve().parent.parent
        self.evaluator = Evaluator(self.db_path, repo_root, self.seeds)
        requeued = self.evaluator.requeue_unfinished()
        if requeued:
            print(f"re-queued {requeued} unfinished evaluation(s)")
        self.evaluator.start()


class BoardHandler(BaseHTTPRequestHandler):
    server: BoardServer
    server_version = "TrafficBoard/1.0"

    # -- plumbing -----------------------------------------------------------

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass  # keep the console quiet during the workshop

    def _send(self, status: int, content_type: str, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _html(self, page: str, status: int = 200) -> None:
        self._send(status, "text/html; charset=utf-8", page.encode("utf-8"))

    def _json(self, obj, status: int = 200) -> None:
        self._send(
            status, "application/json", json.dumps(obj).encode("utf-8")
        )

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD_BYTES:
            raise ValueError(
                f"upload too large ({length} bytes, limit {MAX_UPLOAD_BYTES})"
            )
        return self.rfile.read(length)

    # -- routing ------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        path = urlparse(self.path).path
        if path == "/":
            return self._html(pages.INDEX_HTML)
        if path == "/signup":
            return self._html(pages.signup_page())
        if path == "/health":
            return self._json({"ok": True, "backlog": self.server.evaluator.backlog})
        if path == "/api/leaderboard":
            return self._api_leaderboard()
        parts = [p for p in path.split("/") if p]
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "participant":
            return self._api_participant(parts[2])
        if len(parts) == 2 and parts[0] == "p":
            person = db.participant_by_token(self.server.db_path, parts[1])
            if person:
                return self._html(pages.ME_HTML)
        self._html(pages.NOT_FOUND_HTML, status=404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        path = urlparse(self.path).path
        try:
            body = self._read_body()
        except ValueError as exc:
            return self._html(pages.signup_page(str(exc)), status=413)
        fields = parse_form(self.headers.get("Content-Type", ""), body)

        if path == "/signup":
            return self._post_signup(fields)
        parts = [p for p in path.split("/") if p]
        if len(parts) == 3 and parts[0] == "p" and parts[2] == "upload":
            return self._post_upload(parts[1], fields)
        self._html(pages.NOT_FOUND_HTML, status=404)

    # -- handlers -----------------------------------------------------------

    def _post_signup(self, fields: Dict[str, bytes]) -> None:
        raw_name = fields.get("name", b"").decode("utf-8", "replace")
        try:
            person = db.create_participant(self.server.db_path, raw_name)
        except db.SignupError as exc:
            return self._html(pages.signup_page(str(exc)), status=400)
        self._redirect(
            f"/p/{person['token']}?msg="
            + quote("Welcome! Bookmark this page - it is your secret upload link.")
        )

    def _post_upload(self, token: str, fields: Dict[str, bytes]) -> None:
        person = db.participant_by_token(self.server.db_path, token)
        if person is None:
            return self._html(pages.NOT_FOUND_HTML, status=404)

        back = f"/p/{token}"

        def bounce(message: str) -> None:
            self._redirect(f"{back}?kind=err&msg={quote(message)}")

        elapsed = time.time() - db.last_submission_at(
            self.server.db_path, person["id"]
        )
        if elapsed < UPLOAD_COOLDOWN_S:
            return bounce(
                f"Easy there - wait {UPLOAD_COOLDOWN_S - int(elapsed)}s between uploads."
            )

        code = fields.get("file") or b""
        if not code.strip():
            code = fields.get("code") or b""
        if not code.strip():
            return bounce("No code received - choose a file or paste your policy.")
        if len(code) > MAX_UPLOAD_BYTES:
            return bounce(f"Code too large (limit {MAX_UPLOAD_BYTES // 1000} kB).")
        try:
            text = code.decode("utf-8")
        except UnicodeDecodeError:
            return bounce("File is not valid UTF-8 text - upload your policy.py source.")
        if "class Policy" not in text:
            return bounce("Your code must define `class Policy` (see the template).")

        submission_id = db.create_submission(self.server.db_path, person["id"])
        code_dir = self.server.uploads_dir / f"p{person['id']:04d}"
        code_dir.mkdir(parents=True, exist_ok=True)
        code_path = code_dir / f"s{submission_id:05d}.py"
        code_path.write_text(text)
        db.set_submission_code_path(
            self.server.db_path, submission_id, str(code_path)
        )
        self.server.evaluator.submit(submission_id)
        self._redirect(
            f"{back}?msg="
            + quote("Submission received - evaluating now. Results appear below in a few seconds.")
        )

    # -- API ------------------------------------------------------------------

    @staticmethod
    def _scenario_scores(detail: Optional[Dict]) -> Dict[str, float]:
        if not detail:
            return {}
        return {
            s["scenario"]: s["mean_score"] for s in detail.get("scenarios", [])
        }

    def _api_leaderboard(self) -> None:
        entries = db.leaderboard(self.server.db_path)
        standings = []
        for entry in entries:
            standings.append(
                {
                    "name": entry["name"],
                    "best_score": entry["best_score"],
                    "scenario_scores": self._scenario_scores(entry["best_detail"]),
                    "attempts": entry["attempts"],
                    "last_activity": entry["last_activity"],
                    "latest_status": entry["latest_status"],
                    "latest_error": entry["latest_error"],
                }
            )
        self._json(
            {
                "generated_at": time.time(),
                "seeds": list(self.server.seeds),
                "scenarios": [
                    {"name": s.name, "title": s.title} for s in SCENARIOS.values()
                ],
                "backlog": self.server.evaluator.backlog,
                "standings": standings,
            }
        )

    def _api_participant(self, token: str) -> None:
        person = db.participant_by_token(self.server.db_path, token)
        if person is None:
            return self._json({"error": "unknown token"}, status=404)
        submissions = []
        best = None
        for sub in db.submissions_for(self.server.db_path, person["id"]):
            detail = json.loads(sub["detail_json"]) if sub["detail_json"] else None
            if sub["status"] == "scored" and (
                best is None or sub["total_score"] > best
            ):
                best = sub["total_score"]
            submissions.append(
                {
                    "created_at": sub["created_at"],
                    "status": sub["status"],
                    "total_score": sub["total_score"],
                    "error": sub["error"],
                    "scenario_scores": self._scenario_scores(detail),
                }
            )
        self._json(
            {"name": person["name"], "best_score": best, "submissions": submissions}
        )


def serve(
    host: str = "0.0.0.0",
    port: int = 8000,
    data_dir: str = "server_data",
    seeds: Optional[Sequence[int]] = None,
) -> BoardServer:
    server = BoardServer((host, port), Path(data_dir), seeds)
    return server
