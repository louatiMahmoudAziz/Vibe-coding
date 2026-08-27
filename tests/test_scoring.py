"""Scoring formula behavior and bounds."""

import unittest

from traffic_sim.engine import RunResult, Vehicle
from traffic_sim.metrics import (
    STARVATION_PENALTY_CAP,
    STARVATION_THRESHOLD,
    ScenarioScore,
    failed_run,
    score_run,
    total_score,
)


def _result(vehicles, horizon=900):
    return RunResult("synthetic", 1, horizon, vehicles=vehicles)


class TestScoreRun(unittest.TestCase):
    def test_perfect_service_scores_100(self):
        vehicles = [Vehicle("N_straight", t, departed=t) for t in range(100)]
        metrics = score_run(_result(vehicles))
        self.assertAlmostEqual(metrics.score, 100.0)
        self.assertEqual(metrics.starved, 0)

    def test_no_arrivals_scores_100(self):
        metrics = score_run(_result([]))
        self.assertAlmostEqual(metrics.score, 100.0)

    def test_nobody_served_scores_zero_or_near(self):
        vehicles = [Vehicle("N_straight", 0) for _ in range(50)]
        metrics = score_run(_result(vehicles, horizon=900))
        self.assertEqual(metrics.served, 0)
        self.assertAlmostEqual(metrics.throughput_pts, 0.0)
        # 900 s censored wait obliterates latency points and triggers starvation.
        self.assertAlmostEqual(metrics.score, 0.0)

    def test_unserved_vehicles_wait_censored_at_horizon(self):
        vehicles = [Vehicle("N_straight", 100)]
        metrics = score_run(_result(vehicles, horizon=400))
        self.assertEqual(metrics.max_wait, 300)
        self.assertEqual(metrics.starved, 1)

    def test_starvation_threshold_and_cap(self):
        served_fast = [Vehicle("N_straight", t, departed=t) for t in range(200)]
        starved = [
            Vehicle("E_left", 0, departed=STARVATION_THRESHOLD + 1)
            for _ in range(50)
        ]
        metrics = score_run(_result(served_fast + starved))
        self.assertEqual(metrics.starved, 50)
        self.assertEqual(metrics.starvation_penalty, STARVATION_PENALTY_CAP)

    def test_score_never_negative(self):
        vehicles = [Vehicle("N_straight", 0) for _ in range(500)]
        metrics = score_run(_result(vehicles, horizon=2000))
        self.assertGreaterEqual(metrics.score, 0.0)

    def test_latency_tradeoff_monotonic(self):
        fast = [Vehicle("N_straight", t, departed=t + 5) for t in range(100)]
        slow = [Vehicle("N_straight", t, departed=t + 90) for t in range(100)]
        self.assertGreater(
            score_run(_result(fast)).score, score_run(_result(slow)).score
        )


class TestAggregation(unittest.TestCase):
    def test_failed_run_scores_zero_with_error(self):
        metrics = failed_run("balanced_commute", 7, "boom")
        self.assertEqual(metrics.score, 0.0)
        self.assertEqual(metrics.error, "boom")

    def test_total_score_weighted_mean(self):
        a = ScenarioScore("a", weight=1.0, runs=[failed_run("a", 1, "x")])
        vehicles = [Vehicle("N_straight", t, departed=t) for t in range(10)]
        good = score_run(_result(vehicles))
        b = ScenarioScore("b", weight=1.0, runs=[good])
        self.assertAlmostEqual(total_score([a, b]), 50.0)

    def test_total_score_empty(self):
        self.assertEqual(total_score([]), 0.0)


if __name__ == "__main__":
    unittest.main()
