"""The five evaluation scenarios.

Each scenario defines, per lane, a piecewise-constant arrival rate in
vehicles per second. Rates are Bernoulli probabilities per 1-second tick,
so they must stay below 1.0 (realistic urban values are well below 0.5).

Reference capacity: with two lanes open at saturation flow the intersection
serves at most 1.0 veh/s while green, and every phase change burns 4 seconds
of yellow + all-red plus 2 seconds of startup lost time. Sustained demand
above ~0.75 veh/s total therefore requires very efficient phase allocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from .engine import LANES

# (start_second_inclusive, end_second_exclusive, rate_veh_per_second)
Segment = Tuple[int, int, float]
RateTable = Dict[str, Tuple[Segment, ...]]


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    description: str
    horizon: int
    weight: float
    rates: RateTable

    def rate(self, lane: str, t: int) -> float:
        for start, end, rate in self.rates.get(lane, ()):
            if start <= t < end:
                return rate
        return 0.0

    def expected_arrivals(self) -> float:
        total = 0.0
        for segments in self.rates.values():
            for start, end, rate in segments:
                total += (end - start) * rate
        return total


def _flat(horizon: int, straight: float, left: float, lanes=LANES) -> RateTable:
    table: RateTable = {}
    for lane in lanes:
        rate = left if lane.endswith("_left") else straight
        table[lane] = ((0, horizon, rate),)
    return table


def _build_scenarios() -> Dict[str, Scenario]:
    scenarios = {}

    # ------------------------------------------------------------------ #
    # 1. Balanced commute: moderate symmetric demand. The sanity check.
    # ------------------------------------------------------------------ #
    horizon = 900
    scenarios["balanced_commute"] = Scenario(
        name="balanced_commute",
        title="Balanced Commute",
        description=(
            "Moderate, symmetric demand on all approaches for 15 minutes. "
            "A reasonable policy should serve nearly everyone quickly."
        ),
        horizon=horizon,
        weight=1.0,
        rates=_flat(horizon, straight=0.08, left=0.03),
    )

    # ------------------------------------------------------------------ #
    # 2. Rush hour: heavy N/S through-traffic, light everywhere else.
    #    Rewards asymmetric green allocation; punishes rigid 25/25/25/25.
    # ------------------------------------------------------------------ #
    horizon = 900
    rates: RateTable = {
        "N_straight": ((0, horizon, 0.22),),
        "S_straight": ((0, horizon, 0.22),),
        "N_left": ((0, horizon, 0.05),),
        "S_left": ((0, horizon, 0.05),),
        "E_straight": ((0, horizon, 0.05),),
        "W_straight": ((0, horizon, 0.05),),
        "E_left": ((0, horizon, 0.02),),
        "W_left": ((0, horizon, 0.02),),
    }
    scenarios["rush_hour_ns"] = Scenario(
        name="rush_hour_ns",
        title="North-South Rush Hour",
        description=(
            "Heavy through-traffic on the North-South axis with light "
            "cross-traffic. Give the main artery the green time it needs "
            "without starving the side streets and left-turners."
        ),
        horizon=horizon,
        weight=1.0,
        rates=rates,
    )

    # ------------------------------------------------------------------ #
    # 3. Flash crowd: quiet, then a stadium lets out onto E/W for 4 min.
    #    Rewards fast detection of and recovery from a demand spike.
    # ------------------------------------------------------------------ #
    horizon = 1200
    burst_start, burst_end = 300, 540
    rates = {}
    for lane in LANES:
        base = 0.025 if lane.endswith("_straight") else 0.012
        if lane in ("E_straight", "W_straight"):
            rates[lane] = (
                (0, burst_start, base),
                (burst_start, burst_end, 0.30),
                (burst_end, horizon, base),
            )
        elif lane in ("E_left", "W_left"):
            rates[lane] = (
                (0, burst_start, base),
                (burst_start, burst_end, 0.08),
                (burst_end, horizon, base),
            )
        else:
            rates[lane] = ((0, horizon, base),)
    scenarios["flash_crowd"] = Scenario(
        name="flash_crowd",
        title="Flash Crowd",
        description=(
            "A quiet grid until a stadium empties: East-West demand spikes "
            "hard for four minutes, then fades. Detect the surge, absorb it, "
            "and drain the residual queues before time runs out."
        ),
        horizon=horizon,
        weight=1.0,
        rates=rates,
    )

    # ------------------------------------------------------------------ #
    # 4. Night trickle: sparse arrivals. Latency dominates the score;
    #    a fixed cycle makes lone drivers idle at empty crossings.
    # ------------------------------------------------------------------ #
    horizon = 900
    scenarios["night_trickle"] = Scenario(
        name="night_trickle",
        title="Night Trickle",
        description=(
            "3 a.m. traffic: a car every so often, from random directions. "
            "Throughput is easy; the win is not making a lone driver sit at "
            "an empty intersection while phantom phases cycle."
        ),
        horizon=horizon,
        weight=1.0,
        rates=_flat(horizon, straight=0.015, left=0.006),
    )

    # ------------------------------------------------------------------ #
    # 5. Gridlock stress: near-capacity demand that tilts NS -> EW at
    #    half-time. Rewards throughput efficiency and starvation control.
    # ------------------------------------------------------------------ #
    horizon = 1200
    half = horizon // 2
    rates = {
        "N_straight": ((0, half, 0.16), (half, horizon, 0.10)),
        "S_straight": ((0, half, 0.16), (half, horizon, 0.10)),
        "N_left": ((0, half, 0.07), (half, horizon, 0.04)),
        "S_left": ((0, half, 0.07), (half, horizon, 0.04)),
        "E_straight": ((0, half, 0.10), (half, horizon, 0.16)),
        "W_straight": ((0, half, 0.10), (half, horizon, 0.16)),
        "E_left": ((0, half, 0.04), (half, horizon, 0.07)),
        "W_left": ((0, half, 0.04), (half, horizon, 0.07)),
    }
    scenarios["gridlock_stress"] = Scenario(
        name="gridlock_stress",
        title="Gridlock Stress Test",
        description=(
            "Twenty minutes at ~95% of practical capacity, with the dominant "
            "axis flipping from North-South to East-West at half-time. Every "
            "wasted second of green shows up in the score, and left-turn "
            "lanes are one bad policy away from starvation."
        ),
        horizon=horizon,
        weight=1.0,
        rates=rates,
    )

    return scenarios


SCENARIOS: Dict[str, Scenario] = _build_scenarios()

# Public seeds used for local development and the live leaderboard.
# Organizers re-run the final evaluation with hidden seeds (see docs).
DEFAULT_SEEDS: Tuple[int, ...] = (101, 202, 303)
