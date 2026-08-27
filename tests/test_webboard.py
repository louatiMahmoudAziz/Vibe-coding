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
        person = db.create_participant(self.db_path, "  Team   Rocket ")
        self.assertEqual(person["name"], "Team Rocket")
        self.assertTrue(person["token"])
        with self.assertRaises(db.SignupError):
            db.create_participant(self.db_path, "team rocket")  # case-insensitive

    def test_name_validation(self):
        for bad in ("", "x", "a" * 41, "<script>"):
            with self.assertRaises(db.SignupError):
                db.create_participant(self.db_path, bad)

    def test_leaderboard_ranks_by_best_then_first(self):
        alice = db.create_participant(self.db_path, "Alice")
        bob = db.create_participant(self.db_path, "Bob")
        for person, score in ((alice, 50.0), (bob, 70.0), (alice, 70.0)):
            sub = db.create_submission(self.db_path, person["id"])
            db.set_submission_code_path(self.db_path, sub, "x.py")
            db.finish_submission(self.db_path, sub, score, 10.0, {"scenarios": []}, None)
        board = db.leaderboard(self.db_path)
        # Bob reached 70 first, so he outranks Alice despite the tie.
        self.assertEqual([e["name"] for e in board], ["Bob", "Alice"])
        self.assertEqual(board[0]["best_score"], 70.0)
        self.assertEqual(board[1]["attempts"], 2)


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

    def _post(self, path, data, content_type, follow=False):
        request = urllib.request.Request(
            self.base + path, data=data, headers={"Content-Type": content_type}
        )
        if follow:
            return urllib.request.urlopen(request, timeout=10)

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        try:
            return opener.open(request, timeout=10)
        except urllib.error.HTTPError as response:
            return response  # 303 arrives here with NoRedirect

    def test_full_flow_signup_upload_score(self):
        # 1. Pages are served.
        with urllib.request.urlopen(self.base + "/", timeout=10) as response:
            self.assertIn("Traffic Flow Challenge", response.read().decode())

        # 2. Sign up -> redirected to a personal page with a token.
        response = self._post(
            "/signup", b"name=The+Testers", "application/x-www-form-urlencoded"
        )
        self.assertEqual(response.status, 303)
        location = response.headers["Location"]
        self.assertTrue(location.startswith("/p/"))
        token = location.split("/p/")[1].split("?")[0]

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
        self.assertEqual(len(entry["scenario_scores"]), 5)

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
            "/signup", b"name=Broken+Bots", "application/x-www-form-urlencoded"
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
