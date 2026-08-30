"""The evaluation traces, grouped into three acts.

Each scenario defines, per approach, a piecewise-constant arrival rate in
vehicles per second. Rates are Bernoulli probabilities per 1-second tick,
so they must stay below 1.0 (realistic urban values are well below 0.5).

Reference capacity
------------------
Two approaches are open at once, each discharging at 0.5 veh/s, so the
intersection moves 1.0 veh/s while a green is actually running. Every full
cycle of the two phases burns 12 s of dead time (2 changes x [3 s yellow +
1 s all-red + 2 s startup lost]). Sustained capacity is therefore
(C - 12) / C veh/s: 0.70 at a 40 s cycle, 0.80 at 60 s, 0.85 at 80 s.

Every trace below sits BELOW that line. Difficulty comes from the shape of
demand, not from making the problem unwinnable.
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


def _flat(horizon: int, ns: float, ew: float) -> RateTable:
    return {
        "north": ((0, horizon, ns),),
        "south": ((0, horizon, ns),),
        "east": ((0, horizon, ew),),
        "west": ((0, horizon, ew),),
    }


def _build_scenarios() -> Dict[str, Scenario]:
    scenarios: Dict[str, Scenario] = {}

    # ------------------------------------------------------------------ #
    # ACT 1 - the pilot. Moderate, near-symmetric, comfortably winnable.
    # A lazy prompt should pass this. That is the point: Act 1 exists to
    # get code on the board and make people feel fast, not to filter.
    # Total demand 0.42 veh/s, about half of capacity.
    # ------------------------------------------------------------------ #
    scenarios["pilot_morning"] = Scenario(
        name="pilot_morning",
        title="Monday, 6:40 a.m.",
        description=(
            "A normal weekday at the pilot intersection. Traffic on all four "
            "approaches, a little heavier north-south than east-west."
        ),
        horizon=600,
        weight=1.0,
        act="act1",
        rates=_flat(600, ns=0.120, ew=0.090),
    )

    # ------------------------------------------------------------------ #
    # ACT 2 - two complaints, two OPPOSITE failure modes.
    #
    # This is the heart of the challenge. The fix for one complaint is the
    # cause of the other, and a controller has to satisfy both at once.
    # ------------------------------------------------------------------ #

    # Complaint 1: the avenue backs up in the evening rush.
    #
    # Demand is 0.52 veh/s -- still only 65% of capacity, so this is very
    # winnable. But every phase change burns 6 s of dead time, and a
    # controller that switches the moment the other queue is longer flips
    # ~54 times in ten minutes. That is 5.4 minutes of a 10-minute run with
    # nobody moving. Measured: greedy switching serves 77% of traffic with a
    # 56 s average wait; anything with switching discipline serves 97% at
    # 16 s. The lesson is that switching is not free.
    scenarios["rush_evening"] = Scenario(
        name="rush_evening",
        title="Thursday, 5:50 p.m.",
        description=(
            "The evening rush, heavy from every direction. Traffic is well "
            "under what the intersection can move -- if you stop wasting "
            "green time on changing the lights."
        ),
        horizon=600,
        weight=1.0,
        act="act2",
        rates=_flat(600, ns=0.130, ew=0.130),
    )

    # Complaint 2: the side street never gets a green.
    #
    # The avenue takes 0.19 veh/s per approach (a car every ~5 s); the side
    # street takes 0.018 (a car every ~55 s). A queue of 1 never beats a
    # queue of 12, so the margin you just added to stop the flipping is
    # exactly what keeps the side street red. Measured: a controller with a
    # switching margin leaves someone waiting 188 s here, while its average
    # wait is the BEST in the field at 5.7 s. The dashboard looks perfect.
    scenarios["side_street"] = Scenario(
        name="side_street",
        title="Thursday, 4:15 p.m.",
        description=(
            "The avenue is packed. The side street sees about one car a "
            "minute -- and those are the drivers who called 311."
        ),
        horizon=600,
        weight=1.0,
        act="act2",
        rates=_flat(600, ns=0.190, ew=0.018),
    )

    # ------------------------------------------------------------------ #
    # ACT 3 - deployment. Never shown before the freeze. Four intersections
    # that are nothing like the pilot.
    # ------------------------------------------------------------------ #

    # Almost empty. Punishes a controller that cycles on a timer regardless
    # of whether anyone is waiting: every pointless switch is 6 s of dead
    # time and a red light for a car that could have gone straight through.
    scenarios["deploy_residential"] = Scenario(
        name="deploy_residential",
        title="Bay Ridge, 3 a.m.",
        description="A car every so often, from anywhere. Do not make them wait.",
        horizon=600, weight=1.0, act="deployment", hidden=True,
        rates=_flat(600, ns=0.020, ew=0.020),
    )

    # Heavy east-west corridor: the mirror image of Act 2's avenue. A
    # controller that learned "north-south is the busy one" fails here.
    scenarios["deploy_corridor"] = Scenario(
        name="deploy_corridor",
        title="The Corridor",
        description="Overwhelmingly east-west. The busy road is not the pilot's.",
        horizon=600, weight=1.0, act="deployment", hidden=True,
        rates=_flat(600, ns=0.030, ew=0.250),
    )

    # Quiet, then four minutes of one-directional chaos, then quiet again.
    # Rewards adapting to what is actually queued right now.
    horizon = 720
    burst_a, burst_b = 180, 420
    scenarios["deploy_arena"] = Scenario(
        name="deploy_arena",
        title="Barclays, Game Night",
        description="Nothing, then everything, then nothing. Absorb it and drain it.",
        horizon=horizon, weight=1.0, act="deployment", hidden=True,
        rates={
            "north": ((0, horizon, 0.025),),
            "east": ((0, horizon, 0.025),),
            "west": ((0, horizon, 0.025),),
            "south": ((0, burst_a, 0.025),
                      (burst_a, burst_b, 0.400),
                      (burst_b, horizon, 0.025)),
        },
    )

    # The busy axis flips at half-time. Punishes anything hard-coded to a
    # direction, and anything tuned to the pilot's traffic pattern.
    horizon = 720
    half = horizon // 2
    scenarios["deploy_reversal"] = Scenario(
        name="deploy_reversal",
        title="Queens Boulevard",
        description="Busy north-south all morning, busy east-west all afternoon.",
        horizon=horizon, weight=1.0, act="deployment", hidden=True,
        rates={
            "north": ((0, half, 0.190), (half, horizon, 0.050)),
            "south": ((0, half, 0.190), (half, horizon, 0.050)),
            "east": ((0, half, 0.050), (half, horizon, 0.190)),
            "west": ((0, half, 0.050), (half, horizon, 0.190)),
        },
    )

    return scenarios


ACTS: Tuple[str, ...] = ("act1", "act2", "deployment")

# Which traces score in each act. Later acts re-run everything before them --
# a controller that fixes Act 2 by breaking Act 1 fails Act 1.
ACT_SCENARIOS: Dict[str, Tuple[str, ...]] = {
    "act1": ("pilot_morning",),
    "act2": ("pilot_morning", "rush_evening", "side_street"),
    "deployment": (
        "pilot_morning", "rush_evening", "side_street",
        "deploy_residential", "deploy_corridor", "deploy_arena", "deploy_reversal",
    ),
}

SCENARIOS: Dict[str, Scenario] = _build_scenarios()


def scenarios_for_act(act: str) -> Tuple[Scenario, ...]:
    return tuple(SCENARIOS[n] for n in ACT_SCENARIOS.get(act, ()))


# Public seeds used for local development and the live leaderboard.
# Organizers re-run the final evaluation with hidden seeds (see docs).
DEFAULT_SEEDS: Tuple[int, ...] = (101, 202, 303)
