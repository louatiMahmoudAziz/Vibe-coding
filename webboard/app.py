"""HTTP server: signup, personal upload pages, JSON API, live leaderboard."""

from __future__ import annotations

import json
import time
from email.parser import BytesParser
from email.policy import default as _email_policy
from http import cookies as http_cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Sequence
from urllib.parse import parse_qs, quote, urlparse

from traffic_sim import runner
from traffic_sim.scenarios import DEFAULT_SEEDS, SCENARIOS, scenarios_for_act

from . import db, gateway, pages
from .evaluator import Evaluator

import os

MAX_UPLOAD_BYTES = 200_000
UPLOAD_COOLDOWN_S = 15
SESSION_COOKIE = "board_session"
SESSION_MAX_AGE_S = 30 * 24 * 3600  # stay signed in for 30 days or until logout


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
        gateway.ensure_schema(self.db_path)
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

    def _send(
        self,
        status: int,
        content_type: str,
        payload: bytes,
        set_cookie: Optional[str] = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        self.wfile.write(payload)

    def _html(
        self, page: str, status: int = 200, set_cookie: Optional[str] = None
    ) -> None:
        self._send(
            status, "text/html; charset=utf-8", page.encode("utf-8"), set_cookie
        )

    def _json(self, obj, status: int = 200) -> None:
        self._send(
            status, "application/json", json.dumps(obj).encode("utf-8")
        )

    def _redirect(self, location: str, set_cookie: Optional[str] = None) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()

    # -- sessions -------------------------------------------------------------

    @staticmethod
    def _session_cookie(token: str) -> str:
        return (
            f"{SESSION_COOKIE}={token}; Path=/; Max-Age={SESSION_MAX_AGE_S}; "
            "HttpOnly; SameSite=Lax"
        )

    @staticmethod
    def _logout_cookie() -> str:
        return f"{SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"

    def _session_participant(self) -> Optional[Dict]:
        header = self.headers.get("Cookie")
        if not header:
            return None
        jar = http_cookies.SimpleCookie()
        try:
            jar.load(header)
        except http_cookies.CookieError:
            return None
        morsel = jar.get(SESSION_COOKIE)
        if morsel is None or not morsel.value:
            return None
        return db.participant_by_token(self.server.db_path, morsel.value)

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
        if path in ("/signup", "/login"):
            # Already signed in? Straight to the upload page.
            person = self._session_participant()
            if person:
                return self._redirect(f"/p/{person['token']}")
            page = pages.signup_page() if path == "/signup" else pages.login_page()
            return self._html(page)
        if path == "/me":
            person = self._session_participant()
            if person:
                return self._redirect(f"/p/{person['token']}")
            return self._redirect("/login")
        if path == "/logout":
            return self._redirect("/", set_cookie=self._logout_cookie())
        if path == "/health":
            return self._json(
                {
                    "ok": True,
                    "backlog": self.server.evaluator.backlog,
                    "model": gateway.MODEL,
                    "fallback_model": gateway.MODEL_FALLBACK,
                    "thinking_budget": gateway.THINKING_BUDGET,
                    "max_output_tokens": gateway.MAX_OUTPUT_TOKENS,
                    "temperature": gateway.TEMPERATURE,
                    "key_source": gateway.key_source(),
                    "key_check": gateway.key_check(),
                    "identity_mode": gateway.identity_mode(),
                    "ai_queue_depth": gateway.queue_depth(),
                }
            )
        if path == "/api/session":
            person = self._session_participant()
            if person:
                return self._json(
                    {"authenticated": True, "name": person["name"]}
                )
            return self._json({"authenticated": False})
        if path == "/api/leaderboard":
            return self._api_leaderboard()
        if path == "/api/act":
            person = self._session_participant()
            if person is None:
                return self._json({"act": "act1", "acts": list(db.ACTS),
                                   "cleared": []})
            return self._json(
                {
                    "act": db.participant_act(self.server.db_path, person["id"]),
                    "acts": list(db.ACTS),
                    "cleared": db.acts_cleared(self.server.db_path, person["id"]),
                }
            )
        if path == "/api/budget":
            return self._api_budget()
        parts = [p for p in path.split("/") if p]
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "replay":
            return self._api_replay(parts[2], parts[3])
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "participant":
            return self._api_participant(parts[2])
        if len(parts) == 2 and parts[0] == "p":
            person = db.participant_by_token(self.server.db_path, parts[1])
            if person:
                # Opening a valid personal link signs this browser in
                # (the link is the credential, like a magic link).
                return self._html(
                    pages.ME_HTML, set_cookie=self._session_cookie(parts[1])
                )
        self._html(pages.NOT_FOUND_HTML, status=404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        path = urlparse(self.path).path
        try:
            body = self._read_body()
        except ValueError as exc:
            if path.startswith("/api/"):
                return self._json({"error": str(exc)}, status=413)
            return self._html(pages.signup_page(str(exc)), status=413)

        # JSON endpoint: handled before the form parser touches the body.
        if path == "/api/generate":
            return self._api_generate(body)
        fields = parse_form(self.headers.get("Content-Type", ""), body)

        if path == "/signup":
            return self._post_signup(fields)
        if path == "/login":
            return self._post_login(fields)
        parts = [p for p in path.split("/") if p]
        if len(parts) == 3 and parts[0] == "p" and parts[2] == "upload":
            return self._post_upload(parts[1], fields)
        self._html(pages.NOT_FOUND_HTML, status=404)

    # -- handlers -----------------------------------------------------------


    def _api_replay(self, submission_id: str, scenario: str) -> None:
        """Re-run one scored submission so the browser can animate it.

        Recomputed rather than stored: a run is about 0.03 s, so caching would
        cost more than it saves. The participant must own the submission.
        """
        person = self._session_participant()
        if person is None:
            return self._json({"error": "Sign in first."}, status=401)
        try:
            row = db.submission(self.server.db_path, int(submission_id))
        except (TypeError, ValueError):
            return self._json({"error": "Bad submission id."}, status=400)
        if row is None or row["participant_id"] != person["id"]:
            return self._json({"error": "Not found."}, status=404)
        if not row["code_path"]:
            return self._json({"error": "That submission has no code."}, status=404)
        if scenario not in SCENARIOS:
            return self._json({"error": "No such scenario."}, status=404)
        try:
            payload = runner.replay(Path(row["code_path"]), scenario)
        except Exception as exc:  # noqa: BLE001 - participant code can fail anyhow
            return self._json({"error": f"Could not replay: {exc}"}, status=500)
        return self._json(payload)


    # -- AI gateway ---------------------------------------------------------

    def _api_budget(self) -> None:
        """How much AI budget this participant has left."""
        person = self._session_participant()
        if person is None:
            return self._json({"error": "not signed in"}, status=401)
        return self._json(
            {
                "budget": gateway.budget_state(self.server.db_path, person["id"]),
                "queue_depth": gateway.queue_depth(),
            }
        )

    def _api_generate(self, body: bytes) -> None:
        """Spend AI budget to produce a controller.

        The only route from a participant to the model. Authenticated by
        the session cookie, metered by the gateway, and rate-shaped so a
        room full of people submitting at once does not trip the provider's
        limits. The API key never leaves the server.
        """
        person = self._session_participant()
        if person is None:
            return self._json({"error": "Sign in first."}, status=401)

        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return self._json({"error": "Body must be JSON."}, status=400)
        if not isinstance(payload, dict):
            return self._json({"error": "Body must be a JSON object."}, status=400)

        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return self._json({"error": "Tell the AI what to do."}, status=400)
        current_code = payload.get("code") or None
        mode = "ask" if str(payload.get("mode", "build")).lower() == "ask" else "build"

        def budget():
            return gateway.budget_state(self.server.db_path, person["id"])

        try:
            generation = gateway.generate(
                self.server.db_path, person["id"], prompt, current_code, mode
            )
        except gateway.BudgetExhausted:
            return self._json(
                {
                    "error": "Your AI budget is spent. What you have now is what you ship.",
                    "budget": budget(),
                },
                status=402,
            )
        except gateway.GatewayError as exc:
            # Upstream trouble is never charged to the participant.
            return self._json({"error": str(exc), "budget": budget()}, status=502)

        return self._json(
            {
                "mode": generation.mode,
                "answer": generation.raw_text if generation.mode == "ask" else None,
                "code": generation.code,
                "charged": generation.charged,
                "attempts": generation.attempts,
                "note": generation.note,
                "budget": budget(),
            }
        )

    def _post_signup(self, fields: Dict[str, bytes]) -> None:
        raw_name = fields.get("name", b"").decode("utf-8", "replace")
        raw_password = fields.get("password", b"").decode("utf-8", "replace")
        try:
            person = db.create_participant(
                self.server.db_path, raw_name, raw_password
            )
        except db.SignupError as exc:
            return self._html(pages.signup_page(str(exc)), status=400)
        self._redirect(
            f"/p/{person['token']}?msg="
            + quote(
                "Welcome! This is your upload page. You'll stay signed in "
                "on this device until you log out."
            ),
            set_cookie=self._session_cookie(person["token"]),
        )

    def _post_login(self, fields: Dict[str, bytes]) -> None:
        raw_name = fields.get("name", b"").decode("utf-8", "replace")
        raw_password = fields.get("password", b"").decode("utf-8", "replace")
        person = db.authenticate(self.server.db_path, raw_name, raw_password)
        if person is None:
            return self._html(
                pages.login_page("Wrong name or password."), status=401
            )
        self._redirect(
            f"/p/{person['token']}?msg=" + quote("Welcome back!"),
            set_cookie=self._session_cookie(person["token"]),
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

        submission_id = db.create_submission(
            self.server.db_path,
            person["id"],
            db.participant_act(self.server.db_path, person["id"]),
        )
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
        # Average wait, not the old 0-100 composite. Every controller scores
        # 88-97 on that scale, so printing it made a catastrophic policy and an
        # excellent one look identical.
        return {
            s["scenario"]: s["mean_avg_wait"] for s in detail.get("scenarios", [])
        }

    @staticmethod
    def _failed_gates(detail: Optional[Dict]) -> List[str]:
        """Which requirements this submission missed, as short labels.

        The board shows WHY somebody is below the line. "Missed: nobody
        stranded" teaches; a number that is 3 points lower does not.
        """
        if not detail:
            return []
        missed = []
        for scenario in detail.get("scenarios", []):
            for run in scenario.get("runs", []):
                for req in run.get("requirements", []):
                    if not req.get("passed") and req.get("label") not in missed:
                        missed.append(req.get("label"))
        return missed

    def _api_leaderboard(self) -> None:
        entries = db.leaderboard(self.server.db_path)
        # Everyone is on their own act now, so the columns show the widest set
        # anybody has reached rather than one room-wide act.
        act = max((e["act"] for e in entries),
                  key=lambda a: db.ACTS.index(a), default="act1")
        standings = []
        for entry in entries:
            standings.append(
                {
                    "name": entry["name"],
                    "act": entry["act"],
                    "shown_act": entry["shown_act"],
                    "cleared": entry["cleared"],
                    "best_score": entry["best_score"],
                    "best_passed": entry["best_passed"],
                    "best_wait": entry["best_rank_wait"],
                    "best_worst_wait": entry["best_worst_wait"],
                    "failed_gates": self._failed_gates(entry["best_detail"]),
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
                "act": act,
                # Only the traces this act actually scores. Listing all seven
                # printed "7 scenarios per evaluation" above six empty columns.
                "scenarios": [
                    {"name": s.name, "title": s.title}
                    for s in scenarios_for_act(act)
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
                    "id": sub["id"],
                    "created_at": sub["created_at"],
                    "status": sub["status"],
                    "passed_all": (detail or {}).get("passed_all"),
                    "worst_wait": (detail or {}).get("worst_wait"),
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
