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
    act: str = "act1"          # act1 | act2 | deployment
    hidden: bool = False       # deployment traces are never shown before Act 3

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
    """Three acts.

    Capacity, for reference: cycling all four phases costs 24 s of dead time
    (4 changes x [3 s yellow + 1 s all-red + 2 s startup]), so real throughput
    is (C - 24) / C veh/s -- 0.60 at a 60 s cycle, 0.73 at 90 s, 0.80 at 120 s.

    Every trace below sits BELOW that line. The previous rush-hour and gridlock
    traces sat above it, which meant no policy could pass them and the score
    measured nothing but how fast you drowned. Difficulty here comes from the
    shape of demand, not from making the problem unwinnable.
    """
    scenarios = {}

    # ------------------------------------------------------------------ #
    # ACT 1 - the pilot. Moderate, symmetric, comfortably under capacity.
    # A lazy prompt should pass this. That is the point.
    # ------------------------------------------------------------------ #
    horizon = 600
    scenarios["pilot_morning"] = Scenario(
        name="pilot_morning",
        title="Monday Morning",
        description=(
            "The pilot intersection on a normal weekday. Moderate demand, "
            "roughly even on all four approaches."
        ),
        horizon=horizon,
        weight=1.0,
        act="act1",
        rates=_flat(horizon, straight=0.075, left=0.028),
    )

    # ------------------------------------------------------------------ #
    # ACT 2 - the complaint. East-west floods; the left-turn lanes trickle.
    #
    # This is the trap, and it is built deliberately. Left demand is ~1 vehicle
    # per 70 s, so those queues are never long. A controller that switches on
    # queue length alone never sees a reason to serve them, and a switching
    # margin large enough to stop thrashing guarantees they starve. Total
    # demand is 0.46 veh/s -- winnable, but only if you serve the small queues.
    # ------------------------------------------------------------------ #
    horizon = 600
    rates: RateTable = {
        "E_straight": ((0, horizon, 0.150),),
        "W_straight": ((0, horizon, 0.150),),
        "N_straight": ((0, horizon, 0.050),),
        "S_straight": ((0, horizon, 0.050),),
        "N_left": ((0, horizon, 0.014),),
        "S_left": ((0, horizon, 0.014),),
        "E_left": ((0, horizon, 0.014),),
        "W_left": ((0, horizon, 0.014),),
    }
    scenarios["complaint_evening"] = Scenario(
        name="complaint_evening",
        title="Thursday, 4 p.m.",
        description=(
            "East-west through traffic dominates. The left-turn lanes see a "
            "vehicle about once a minute -- and those are the drivers calling 311."
        ),
        horizon=horizon,
        weight=1.0,
        act="act2",
        rates=rates,
    )

    # ------------------------------------------------------------------ #
    # ACT 3 - deployment. Never shown before the freeze. Four intersections
    # with different characters, none of them like the pilot.
    # ------------------------------------------------------------------ #

    # Residential: almost empty. Punishes cycling through phases nobody wants.
    horizon = 600
    scenarios["deploy_residential"] = Scenario(
        name="deploy_residential",
        title="Bay Ridge, 3 a.m.",
        description="A car every so often, from anywhere. Do not make them wait.",
        horizon=horizon, weight=1.0, act="deployment", hidden=True,
        rates=_flat(horizon, straight=0.012, left=0.005),
    )

    # Commuter corridor: extreme one-way demand, the mirror of Act 2.
    horizon = 600
    rates = {
        "N_straight": ((0, horizon, 0.175),),
        "S_straight": ((0, horizon, 0.038),),
        "E_straight": ((0, horizon, 0.055),),
        "W_straight": ((0, horizon, 0.055),),
        "N_left": ((0, horizon, 0.022),),
        "S_left": ((0, horizon, 0.010),),
        "E_left": ((0, horizon, 0.018),),
        "W_left": ((0, horizon, 0.018),),
    }
    scenarios["deploy_corridor"] = Scenario(
        name="deploy_corridor",
        title="Northbound Corridor",
        description="Overwhelmingly one direction. The dominant axis is not the pilot's.",
        horizon=horizon, weight=1.0, act="deployment", hidden=True, rates=rates,
    )

    # Arena: quiet, then four minutes of chaos, then quiet again.
    horizon = 720
    burst_a, burst_b = 180, 420
    rates = {}
    for lane in LANES:
        base = 0.020 if lane.endswith("_straight") else 0.008
        if lane in ("E_straight", "W_straight"):
            rates[lane] = ((0, burst_a, base), (burst_a, burst_b, 0.170), (burst_b, horizon, base))
        elif lane in ("E_left", "W_left"):
            rates[lane] = ((0, burst_a, base), (burst_a, burst_b, 0.042), (burst_b, horizon, base))
        else:
            rates[lane] = ((0, horizon, base),)
    scenarios["deploy_arena"] = Scenario(
        name="deploy_arena",
        title="Barclays, Game Night",
        description="Nothing, then everything, then nothing. Absorb it and drain it.",
        horizon=horizon, weight=1.0, act="deployment", hidden=True, rates=rates,
    )

    # Reversing: the busy axis flips at half-time. Punishes anything hard-coded.
    horizon = 720
    half = horizon // 2
    rates = {
        "N_straight": ((0, half, 0.135), (half, horizon, 0.045)),
        "S_straight": ((0, half, 0.135), (half, horizon, 0.045)),
        "E_straight": ((0, half, 0.045), (half, horizon, 0.135)),
        "W_straight": ((0, half, 0.045), (half, horizon, 0.135)),
        "N_left": ((0, half, 0.024), (half, horizon, 0.012)),
        "S_left": ((0, half, 0.024), (half, horizon, 0.012)),
        "E_left": ((0, half, 0.014), (half, horizon, 0.030)),
        "W_left": ((0, half, 0.014), (half, horizon, 0.030)),
    }
    scenarios["deploy_reversal"] = Scenario(
        name="deploy_reversal",
        title="Queens Boulevard",
        description="Busy north-south all morning, busy east-west all afternoon.",
        horizon=horizon, weight=1.0, act="deployment", hidden=True, rates=rates,
    )

    return scenarios


ACTS: Tuple[str, ...] = ("act1", "act2", "deployment")

# Which traces score in each act. Later acts re-run everything before them --
# a controller that fixes Act 2 by breaking Act 1 fails Act 1.
ACT_SCENARIOS: Dict[str, Tuple[str, ...]] = {
    "act1": ("pilot_morning",),
    "act2": ("pilot_morning", "complaint_evening"),
    "deployment": (
        "pilot_morning", "complaint_evening",
        "deploy_residential", "deploy_corridor", "deploy_arena", "deploy_reversal",
    ),
}


def scenarios_for_act(act: str) -> Tuple[Scenario, ...]:
    return tuple(SCENARIOS[n] for n in ACT_SCENARIOS.get(act, ()))


SCENARIOS: Dict[str, Scenario] = _build_scenarios()

# Public seeds used for local development and the live leaderboard.
# Organizers re-run the final evaluation with hidden seeds (see docs).
DEFAULT_SEEDS: Tuple[int, ...] = (101, 202, 303)
