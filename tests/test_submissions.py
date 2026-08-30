"""End-to-end checks of the runner and the shipped demo submissions."""

import unittest
from pathlib import Path

from traffic_sim.runner import (
    discover_submissions,
    evaluate_submission,
    load_policy_module,
)
from traffic_sim.scenarios import SCENARIOS

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMISSIONS = REPO_ROOT / "submissions"


class TestDiscovery(unittest.TestCase):
    def test_template_is_skipped(self):
        paths = discover_submissions(SUBMISSIONS)
        self.assertTrue(paths, "expected demo submissions to exist")
        for path in paths:
            self.assertNotIn("_template", str(path))
            self.assertEqual(path.name, "policy.py")


class TestDemoSubmissions(unittest.TestCase):
    def test_all_demo_teams_load_and_score(self):
        quick = ["pilot_morning", "deploy_residential"]
        for policy_path in discover_submissions(SUBMISSIONS):
            result = evaluate_submission(policy_path, scenario_names=quick, seeds=[101])
            self.assertIsNone(result.load_error, policy_path)
            self.assertFalse(result.errors, f"{policy_path}: {result.errors}")
            self.assertGreater(result.total, 20.0, policy_path)

    def test_adaptive_beats_fixed_on_quiet_street(self):
        """The core lesson of the workshop must hold in the harness.

        Note which controller is used here. team_max_pressure -- greedy with a
        switching margin -- is actually WORSE than a fixed timer on an empty
        street, because it waits for a queue difference that never arrives.
        That is the Act 2 trap, and it is deliberate. The controller that
        beats the timer is the one that bounds waiting.
        """
        fixed = evaluate_submission(
            SUBMISSIONS / "team_fixed_timer" / "policy.py",
            scenario_names=["deploy_residential"],
            seeds=[101, 202],
        )
        adaptive = evaluate_submission(
            SUBMISSIONS.parent / "solutions" / "act2_ceiling.py",
            scenario_names=["deploy_residential"],
            seeds=[101, 202],
        )
        self.assertGreater(adaptive.total, fixed.total)


class TestCrashHandling(unittest.TestCase):
    def _write_policy(self, tmp_path: Path, body: str) -> Path:
        policy = tmp_path / "policy.py"
        policy.write_text(body)
        return policy

    def test_crashing_policy_scores_zero_not_raises(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            policy = self._write_policy(
                Path(tmp),
                "TEAM_NAME='Crash'\n"
                "class Policy:\n"
                "    def decide(self, obs):\n"
                "        raise RuntimeError('kaboom')\n",
            )
            result = evaluate_submission(
                policy, scenario_names=["deploy_residential"], seeds=[101]
            )
            self.assertIsNone(result.load_error)
            self.assertEqual(result.total, 0.0)
            self.assertIn("kaboom", result.errors[0])

    def test_syntax_error_reported_as_load_error(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            policy = self._write_policy(Path(tmp), "def broken(:\n")
            result = evaluate_submission(
                policy, scenario_names=["deploy_residential"], seeds=[101]
            )
            self.assertIsNotNone(result.load_error)
            self.assertEqual(result.total, 0.0)

    def test_missing_policy_class_is_load_error(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            policy = self._write_policy(Path(tmp), "TEAM_NAME = 'NoClass'\n")
            result = evaluate_submission(
                policy, scenario_names=["deploy_residential"], seeds=[101]
            )
            self.assertIsNotNone(result.load_error)
            self.assertIn("Policy", result.load_error)


class TestModuleLoading(unittest.TestCase):
    def test_modules_are_isolated(self):
        path = SUBMISSIONS / "team_fixed_timer" / "policy.py"
        first = load_policy_module(path)
        second = load_policy_module(path)
        self.assertIsNot(first, second)


if __name__ == "__main__":
    unittest.main()
