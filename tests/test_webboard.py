"""Web leaderboard server: unit tests plus a full signup->upload->score flow."""

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from webboard import db
from webboard.app import BoardServer, parse_form

REPO_ROOT = Path(__file__).resolve().parent.parent
GREEDY_CODE = (REPO_ROOT / "submissions" / "team_greedy_queue" / "policy.py").read_text()


class TestFormParsing(unittest.TestCase):
    def test_urlencoded(self):
        fields = parse_form(
            "application/x-www-form-urlencoded", b"name=Ada+Lovelace&x=1"
        )
        self.assertEqual(fields["name"], b"Ada Lovelace")

    def test_multipart_file_and_text(self):
        boundary = "XBOUNDARY"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="policy.py"\r\n'
            "Content-Type: text/x-python\r\n\r\n"
            "class Policy: pass\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="code"\r\n\r\n'
            "pasted\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        fields = parse_form(f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual(fields["file"], b"class Policy: pass")
        self.assertEqual(fields["code"], b"pasted")


class TestDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "board.sqlite3"
        db.init(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_signup_and_duplicate_rejection(self):
        person = db.create_participant(self.db_path, "  Team   Rocket ", "hunter2")
        self.assertEqual(person["name"], "Team Rocket")
        self.assertTrue(person["token"])
        with self.assertRaises(db.SignupError):
            db.create_participant(self.db_path, "team rocket", "x" * 8)  # case-insensitive

    def test_name_validation(self):
        for bad in ("", "x", "a" * 41, "<script>"):
            with self.assertRaises(db.SignupError):
                db.create_participant(self.db_path, bad, "hunter2")

    def test_password_validation(self):
        for bad in ("", "abc", "x" * 65):
            with self.assertRaises(db.SignupError):
                db.create_participant(self.db_path, "Valid Name", bad)

    def test_authenticate(self):
        created = db.create_participant(self.db_path, "Login Team", "s3cret")
        person = db.authenticate(self.db_path, "login team", "s3cret")
        self.assertIsNotNone(person)
        self.assertEqual(person["token"], created["token"])
        self.assertIsNone(db.authenticate(self.db_path, "Login Team", "wrong"))
        self.assertIsNone(db.authenticate(self.db_path, "Nobody", "s3cret"))

    def test_passwords_are_hashed_not_stored(self):
        db.create_participant(self.db_path, "Hash Check", "plaintext-pw")
        with db.connect(self.db_path) as conn:
            row = conn.execute("SELECT password_hash FROM participants").fetchone()
        self.assertNotIn("plaintext-pw", row["password_hash"])
        self.assertTrue(row["password_hash"].startswith("pbkdf2_sha256$"))

    def test_migration_of_pre_password_database(self):
        legacy_path = Path(self.tmp.name) / "legacy.sqlite3"
        with db.connect(legacy_path) as conn:
            conn.execute(
                "CREATE TABLE participants (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
                "token TEXT NOT NULL UNIQUE, created_at REAL NOT NULL)"
            )
            conn.execute(
                "INSERT INTO participants (name, token, created_at) "
                "VALUES ('Old Timer', 'legacy-token', 1.0)"
            )
        db.init(legacy_path)  # must add password_hash without losing data
        person = db.participant_by_token(legacy_path, "legacy-token")
        self.assertEqual(person["name"], "Old Timer")
        # Legacy accounts have no password, so login is refused (token still works).
        self.assertIsNone(db.authenticate(legacy_path, "Old Timer", "anything"))
        # New accounts work normally on the migrated database.
        db.create_participant(legacy_path, "New Kid", "s3cret")
        self.assertIsNotNone(db.authenticate(legacy_path, "New Kid", "s3cret"))

    def _finish(self, person, *, passed, avg, p95=0.0, score=50.0):
        sub = db.create_submission(self.db_path, person["id"])
        db.set_submission_code_path(self.db_path, sub, "x.py")
        db.finish_submission(
            self.db_path, sub, score, avg,
            {"scenarios": [], "passed_all": passed,
             "mean_p95_wait": p95, "worst_wait": int(p95)},
            None,
        )
        return sub

    def test_requirements_outrank_averages(self):
        """The whole point of the board: an unacceptable system ranks last.

        Alice's numbers are far better than Bob's. She missed a requirement.
        She loses. If this test ever flips, the leaderboard is teaching people
        to optimise a metric while shipping something nobody can live with.
        """
        alice = db.create_participant(self.db_path, "Alice", "password")
        bob = db.create_participant(self.db_path, "Bob", "password")
        self._finish(alice, passed=False, avg=5.0, score=95.0)
        self._finish(bob, passed=True, avg=20.0, score=60.0)

        board = db.leaderboard(self.db_path)
        self.assertEqual([e["name"] for e in board], ["Bob", "Alice"])
        self.assertTrue(board[0]["best_passed"])
        self.assertFalse(board[1]["best_passed"])

    def test_among_passers_the_tail_breaks_the_tie(self):
        """Same mean wait; the one with the tighter tail wins."""
        steady = db.create_participant(self.db_path, "Steady", "password")
        spiky = db.create_participant(self.db_path, "Spiky", "password")
        self._finish(steady, passed=True, avg=12.0, p95=20.0)
        self._finish(spiky, passed=True, avg=12.0, p95=90.0)

        board = db.leaderboard(self.db_path)
        self.assertEqual([e["name"] for e in board], ["Steady", "Spiky"])

    def test_best_submission_is_the_passing_one_not_the_high_scorer(self):
        """A participant's own best run is chosen by requirements too."""
        person = db.create_participant(self.db_path, "Iterator", "password")
        self._finish(person, passed=False, avg=4.0, score=99.0)
        self._finish(person, passed=True, avg=18.0, score=55.0)

        entry = db.leaderboard(self.db_path)[0]
        self.assertTrue(entry["best_passed"])
        self.assertEqual(entry["attempts"], 2)


class TestServerEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = BoardServer(
            ("127.0.0.1", 0), Path(cls.tmp.name), seeds=(101,)
        )
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.evaluator.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    @staticmethod
    def _open_no_redirect(request):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        try:
            return opener.open(request, timeout=10)
        except urllib.error.HTTPError as response:
            return response  # 3xx/4xx arrive here with NoRedirect

    def _post(self, path, data, content_type, follow=False):
        request = urllib.request.Request(
            self.base + path, data=data, headers={"Content-Type": content_type}
        )
        if follow:
            return urllib.request.urlopen(request, timeout=10)
        return self._open_no_redirect(request)

    def test_full_flow_signup_upload_score(self):
        # 1. Pages are served.
        with urllib.request.urlopen(self.base + "/", timeout=10) as response:
            self.assertIn("Traffic Flow Challenge", response.read().decode())

        # 2. Sign up -> redirected to a personal page with a token.
        response = self._post(
            "/signup",
            b"name=The+Testers&password=swordfish",
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status, 303)
        location = response.headers["Location"]
        self.assertTrue(location.startswith("/p/"))
        token = location.split("/p/")[1].split("?")[0]

        # 2b. Logging in with the same credentials recovers the same page
        #     and starts a session (cookie set).
        response = self._post(
            "/login",
            b"name=the+testers&password=swordfish",
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status, 303)
        self.assertEqual(
            response.headers["Location"].split("?")[0], f"/p/{token}"
        )
        set_cookie = response.headers["Set-Cookie"]
        self.assertIn("board_session=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        cookie = set_cookie.split(";")[0]

        # 2c. With the session cookie: /me redirects to the personal page,
        #     and /api/session reports the signed-in name.
        request = urllib.request.Request(
            self.base + "/me", headers={"Cookie": cookie}
        )
        response = self._open_no_redirect(request)
        self.assertEqual(response.status, 303)
        self.assertEqual(response.headers["Location"], f"/p/{token}")
        request = urllib.request.Request(
            self.base + "/api/session", headers={"Cookie": cookie}
        )
        with urllib.request.urlopen(request, timeout=10) as api_response:
            session = json.loads(api_response.read())
        self.assertEqual(
            session, {"authenticated": True, "name": "The Testers"}
        )

        # 2d. Logout clears the cookie; without it /me bounces to /login.
        response = self._open_no_redirect(
            urllib.request.Request(
                self.base + "/logout", headers={"Cookie": cookie}
            )
        )
        self.assertEqual(response.status, 303)
        self.assertIn("Max-Age=0", response.headers["Set-Cookie"])
        response = self._open_no_redirect(
            urllib.request.Request(self.base + "/me")
        )
        self.assertEqual(response.headers["Location"], "/login")

        # 2e. A wrong password is rejected and starts no session.
        response = self._post(
            "/login",
            b"name=The+Testers&password=nope",
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status, 401)
        self.assertIsNone(response.headers.get("Set-Cookie"))

        # 3. Upload a known-good policy (multipart, like the browser form).
        boundary = "XBOUNDARY"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="policy.py"\r\n'
            "Content-Type: text/x-python\r\n\r\n"
            + GREEDY_CODE
            + f"\r\n--{boundary}--\r\n"
        ).encode()
        response = self._post(
            f"/p/{token}/upload", body, f"multipart/form-data; boundary={boundary}"
        )
        self.assertEqual(response.status, 303)
        self.assertNotIn("kind=err", response.headers["Location"])

        # 4. Poll the API until the evaluation lands.
        deadline = time.time() + 90
        payload = None
        while time.time() < deadline:
            with urllib.request.urlopen(
                self.base + "/api/leaderboard", timeout=10
            ) as response:
                payload = json.loads(response.read())
            if payload["standings"] and payload["standings"][0]["best_score"]:
                break
            time.sleep(0.5)

        self.assertTrue(payload["standings"], "no standings appeared")
        entry = payload["standings"][0]
        self.assertEqual(entry["name"], "The Testers")
        self.assertEqual(entry["latest_status"], "scored")
        self.assertGreater(entry["best_score"], 20.0)
        # The room starts on Act 1, which scores one trace. Later acts add
        # their own and keep every earlier one, so a fix that breaks the
        # pilot shows up as breaking the pilot.
        self.assertEqual(len(entry["scenario_scores"]), 1)
        self.assertIn("pilot_morning", entry["scenario_scores"])

        # 5. Personal API shows the submission history.
        with urllib.request.urlopen(
            self.base + f"/api/participant/{token}", timeout=10
        ) as response:
            me = json.loads(response.read())
        self.assertEqual(me["name"], "The Testers")
        self.assertEqual(len(me["submissions"]), 1)
        self.assertEqual(me["submissions"][0]["status"], "scored")

        # 6. Immediate re-upload is rejected by the cooldown.
        response = self._post(
            f"/p/{token}/upload", body, f"multipart/form-data; boundary={boundary}"
        )
        self.assertIn("kind=err", response.headers["Location"])

    def test_broken_upload_gets_error_status_not_crash(self):
        response = self._post(
            "/signup",
            b"name=Broken+Bots&password=swordfish",
            "application/x-www-form-urlencoded",
        )
        token = response.headers["Location"].split("/p/")[1].split("?")[0]
        bad_code = "class Policy:\n    def decide(self, obs):\n        return 'WARP'\n"
        response = self._post(
            f"/p/{token}/upload",
            b"code=" + urllib.parse.quote(bad_code).encode(),
            "application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status, 303)

        deadline = time.time() + 90
        status = None
        while time.time() < deadline:
            with urllib.request.urlopen(
                self.base + f"/api/participant/{token}", timeout=10
            ) as response:
                me = json.loads(response.read())
            status = me["submissions"][0]["status"]
            if status in ("scored", "error"):
                break
            time.sleep(0.5)
        # Every run fails with an invalid phase -> total 0, but scored cleanly
        # or flagged as error; either way the server stays healthy.
        self.assertIn(status, ("scored", "error"))
        with urllib.request.urlopen(self.base + "/health", timeout=10) as response:
            self.assertTrue(json.loads(response.read())["ok"])

    def test_unknown_token_404(self):
        request = urllib.request.Request(self.base + "/p/not-a-real-token")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
