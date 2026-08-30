"""Engine correctness: determinism, safety interlocks, flow conservation."""

import unittest

from traffic_sim.engine import (
    ALL_RED,
    MIN_GREEN,
    PHASES,
    PolicyError,
    Simulation,
    YELLOW,
)
from traffic_sim.metrics import score_run
from traffic_sim.scenarios import SCENARIOS


class RoundRobinPolicy:
    """Rotate phases on a fixed 20 s cadence."""

    def decide(self, obs):
        return obs.phases[(obs.time // 20) % 4]


class ThrashingPolicy:
    """Adversarial: demands a different phase every single tick."""

    def decide(self, obs):
        current = obs.phases.index(obs.phase)
        return obs.phases[(current + 1) % 4]


class InvalidReturnPolicy:
    def decide(self, obs):
        return "DIAGONAL_WARP"


class StayPutPolicy:
    def decide(self, obs):
        return obs.phase


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_result(self):
        scenario = SCENARIOS["pilot_morning"]
        a = score_run(Simulation(scenario, 42).run(RoundRobinPolicy()))
        b = score_run(Simulation(scenario, 42).run(RoundRobinPolicy()))
        self.assertEqual(a.to_dict(), b.to_dict())

    def test_different_seed_different_arrivals(self):
        scenario = SCENARIOS["pilot_morning"]
        a = Simulation(scenario, 1).run(StayPutPolicy())
        b = Simulation(scenario, 2).run(StayPutPolicy())
        self.assertNotEqual(
            [v.arrived for v in a.vehicles], [v.arrived for v in b.vehicles]
        )


class TestSafetyInterlocks(unittest.TestCase):
    def _timeline(self, policy, scenario_name="pilot_morning", seed=7):
        states = []
        Simulation(SCENARIOS[scenario_name], seed).run(policy, on_tick=states.append)
        return states

    def test_min_green_enforced_against_thrashing(self):
        """Even a policy demanding a switch every tick cannot violate MIN_GREEN."""
        states = self._timeline(ThrashingPolicy())
        green_streak = 0
        for state in states:
            if state.in_transition:
                if green_streak > 0:
                    self.assertGreaterEqual(green_streak, MIN_GREEN)
                green_streak = 0
            else:
                green_streak += 1

    def test_transition_lasts_yellow_plus_all_red(self):
        states = self._timeline(ThrashingPolicy())
        streaks, current = [], 0
        for state in states:
            if state.in_transition:
                current += 1
            elif current:
                streaks.append(current)
                current = 0
        self.assertTrue(streaks, "expected at least one transition")
        self.assertTrue(all(s == YELLOW + ALL_RED for s in streaks))

    def test_no_departures_during_transition(self):
        states = self._timeline(ThrashingPolicy(), "complaint_evening")
        for state in states:
            if state.in_transition:
                self.assertEqual(state.departures, 0)

    def test_invalid_phase_raises(self):
        with self.assertRaises(PolicyError):
            Simulation(SCENARIOS["deploy_residential"], 1).run(InvalidReturnPolicy())


class TestFlowConservation(unittest.TestCase):
    def test_served_never_exceeds_arrived_and_waits_nonnegative(self):
        result = Simulation(SCENARIOS["complaint_evening"], 5).run(RoundRobinPolicy())
        served = [v for v in result.vehicles if v.served]
        self.assertLessEqual(len(served), len(result.vehicles))
        for vehicle in served:
            self.assertGreaterEqual(vehicle.departed, vehicle.arrived)

    def test_saturation_flow_upper_bound(self):
        """A lane can never discharge more than 1 vehicle per 2 seconds of green."""
        result = Simulation(SCENARIOS["deploy_reversal"], 3).run(StayPutPolicy())
        # StayPut keeps NS_STRAIGHT green for the whole 1200 s horizon:
        # per-lane cap is (1200 - startup) * 0.5, two open lanes total.
        served = sum(1 for v in result.vehicles if v.served)
        self.assertLessEqual(served, 2 * (SCENARIOS["deploy_reversal"].horizon // 2))

    def test_stay_put_serves_only_its_own_lanes(self):
        result = Simulation(SCENARIOS["pilot_morning"], 9).run(StayPutPolicy())
        for vehicle in result.vehicles:
            if vehicle.served:
                self.assertIn(vehicle.lane, ("N_straight", "S_straight"))


class TestScenarios(unittest.TestCase):
    def test_all_scenarios_run_with_all_phases_reachable(self):
        for name, scenario in SCENARIOS.items():
            result = Simulation(scenario, 11).run(RoundRobinPolicy())
            self.assertGreater(len(result.vehicles), 0, name)
            self.assertEqual(result.horizon, scenario.horizon)

    def test_rates_are_valid_probabilities(self):
        for scenario in SCENARIOS.values():
            for segments in scenario.rates.values():
                for start, end, rate in segments:
                    self.assertLess(start, end)
                    self.assertGreaterEqual(rate, 0.0)
                    self.assertLess(rate, 0.5)

    def test_phase_names_stable(self):
        # Participants' policies hardcode these names; never rename silently.
        self.assertEqual(
            PHASES, ("NS_STRAIGHT", "NS_LEFT", "EW_STRAIGHT", "EW_LEFT")
        )


if __name__ == "__main__":
    unittest.main()
