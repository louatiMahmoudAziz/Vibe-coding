"""Discrete-time simulator for a signalized four-way intersection.

The world model
---------------
* Four approaches: North, East, South, West.
* Each approach has two lanes:
    - ``<D>_straight`` : straight + right-turn traffic
    - ``<D>_left``     : protected left-turn traffic
* Four green phases, each opening a pair of non-conflicting lanes:
    - ``NS_STRAIGHT`` -> N_straight, S_straight
    - ``NS_LEFT``     -> N_left,     S_left
    - ``EW_STRAIGHT`` -> E_straight, W_straight
    - ``EW_LEFT``     -> E_left,     W_left

Safety rules (enforced by the engine, NOT by participant policies)
------------------------------------------------------------------
* A green phase must be held for at least ``MIN_GREEN`` seconds.
* Every phase change goes through ``YELLOW`` + ``ALL_RED`` seconds during
  which no lane discharges. Switching therefore has a real cost.
* Once a transition starts, the target phase is latched; further requests
  are ignored until the new green begins.

Traffic dynamics
----------------
* Time advances in 1-second ticks.
* Arrivals are Bernoulli draws per lane per second, using rates defined by
  the scenario. A single seeded RNG with a fixed draw order makes every
  (scenario, seed) run fully deterministic.
* An open lane discharges at the saturation flow of one vehicle every
  ``1 / SATURATION_FLOW`` seconds, after ``STARTUP_LOST`` seconds of green
  (drivers reacting when the light turns green).
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from random import Random
from typing import Callable, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------- #
# Static geometry and signal timing constants
# --------------------------------------------------------------------------- #

DIRECTIONS: Tuple[str, ...] = ("N", "E", "S", "W")
TURNS: Tuple[str, ...] = ("straight", "left")
LANES: Tuple[str, ...] = tuple(f"{d}_{t}" for d in DIRECTIONS for t in TURNS)

PHASES: Tuple[str, ...] = ("NS_STRAIGHT", "NS_LEFT", "EW_STRAIGHT", "EW_LEFT")
PHASE_LANES: Dict[str, Tuple[str, str]] = {
    "NS_STRAIGHT": ("N_straight", "S_straight"),
    "NS_LEFT": ("N_left", "S_left"),
    "EW_STRAIGHT": ("E_straight", "W_straight"),
    "EW_LEFT": ("E_left", "W_left"),
}

MIN_GREEN = 6        # seconds a green must be held before it may change
YELLOW = 3           # seconds of yellow on every phase change
ALL_RED = 1          # seconds of all-red clearance on every phase change
STARTUP_LOST = 2     # seconds of green before the first vehicle discharges
SATURATION_FLOW = 0.5  # vehicles / lane / second once flowing (2 s headway)

TRANSITION_TIME = YELLOW + ALL_RED

# Total wall-clock time a policy may spend deciding over one full run.
POLICY_TIME_BUDGET_S = 10.0


class PolicyError(Exception):
    """Raised when a policy breaks the contract (bad return value, timeout)."""


# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #


@dataclass
class Vehicle:
    lane: str
    arrived: int
    departed: Optional[int] = None

    @property
    def served(self) -> bool:
        return self.departed is not None

    def wait(self, horizon: int) -> int:
        return (self.departed if self.departed is not None else horizon) - self.arrived


@dataclass(frozen=True)
class Observation:
    """Everything a policy is allowed to see at one tick."""

    time: int                     # current simulation second
    horizon: int                  # total scenario length in seconds
    phase: str                    # active (or most recent) green phase
    phase_elapsed: int            # seconds the current green has been held
    in_transition: bool           # True while yellow / all-red is running
    transition_remaining: int     # seconds left in the transition (0 if green)
    can_switch: bool              # True if a switch request would be honored now
    queues: Dict[str, int]        # lane -> queued vehicle count
    oldest_wait: Dict[str, int]   # lane -> wait of the front vehicle (0 if empty)
    arrivals_total: int           # vehicles that have arrived so far
    served_total: int             # vehicles that have crossed so far
    min_green: int = MIN_GREEN
    yellow: int = YELLOW
    all_red: int = ALL_RED
    phases: Tuple[str, ...] = PHASES

    @staticmethod
    def phase_for_lane(lane: str) -> str:
        for phase, lanes in PHASE_LANES.items():
            if lane in lanes:
                return phase
        raise KeyError(lane)


@dataclass
class TickState:
    """Snapshot handed to optional on_tick callbacks (used by watch mode/tests)."""

    time: int
    phase: str
    in_transition: bool
    phase_elapsed: int
    queues: Dict[str, int]
    departures: int


@dataclass
class RunResult:
    scenario_name: str
    seed: int
    horizon: int
    vehicles: List[Vehicle] = field(default_factory=list)
    switches: int = 0
    decide_wall_time: float = 0.0


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #


class Simulation:
    """One deterministic run of a scenario against a policy instance."""

    def __init__(self, scenario, seed: int):
        self.scenario = scenario
        self.seed = seed

    def run(
        self,
        policy,
        on_tick: Optional[Callable[[TickState], None]] = None,
    ) -> RunResult:
        scenario = self.scenario
        horizon = scenario.horizon
        rng = Random(f"traffic-flow::{scenario.name}::{self.seed}")

        queues: Dict[str, List[Vehicle]] = {lane: [] for lane in LANES}
        result = RunResult(scenario.name, self.seed, horizon)

        phase = PHASES[0]
        green_elapsed = 0
        in_transition = False
        transition_remaining = 0
        pending: Optional[str] = None
        budgets: Dict[str, float] = {lane: 0.0 for lane in LANES}
        served_total = 0

        if hasattr(policy, "reset"):
            policy.reset()

        for t in range(horizon):
            # -- 0. complete a finished yellow/all-red transition ------------
            if in_transition and transition_remaining <= 0:
                assert pending is not None
                phase = pending
                pending = None
                in_transition = False
                green_elapsed = 0
                for lane in LANES:
                    budgets[lane] = 0.0

            # -- 1. arrivals (fixed lane order keeps the RNG stream stable) --
            for lane in LANES:
                draw = rng.random()
                if draw < scenario.rate(lane, t):
                    vehicle = Vehicle(lane=lane, arrived=t)
                    queues[lane].append(vehicle)
                    result.vehicles.append(vehicle)

            # -- 2. ask the policy where it wants to go ----------------------
            obs = Observation(
                time=t,
                horizon=horizon,
                phase=phase,
                phase_elapsed=green_elapsed,
                in_transition=in_transition,
                transition_remaining=transition_remaining,
                can_switch=(not in_transition) and green_elapsed >= MIN_GREEN,
                queues={lane: len(queues[lane]) for lane in LANES},
                oldest_wait={
                    lane: (t - queues[lane][0].arrived) if queues[lane] else 0
                    for lane in LANES
                },
                arrivals_total=len(result.vehicles),
                served_total=served_total,
            )
            started = _time.perf_counter()
            target = policy.decide(obs)
            result.decide_wall_time += _time.perf_counter() - started
            if result.decide_wall_time > POLICY_TIME_BUDGET_S:
                raise PolicyError(
                    f"policy exceeded the {POLICY_TIME_BUDGET_S:.0f}s "
                    f"wall-clock budget for one run"
                )
            if target is None:
                target = phase
            if target not in PHASE_LANES:
                raise PolicyError(
                    f"decide() returned {target!r}; expected one of {list(PHASES)}"
                )

            # -- 3. signal state machine (safety rules live here) -----------
            if (
                not in_transition
                and target != phase
                and green_elapsed >= MIN_GREEN
            ):
                in_transition = True
                pending = target
                transition_remaining = TRANSITION_TIME
                result.switches += 1

            departures_this_tick = 0
            if in_transition:
                transition_remaining -= 1
            else:
                # -- 4. discharge open lanes at saturation flow -------------
                green_elapsed += 1
                if green_elapsed > STARTUP_LOST:
                    for lane in PHASE_LANES[phase]:
                        budgets[lane] = min(budgets[lane] + SATURATION_FLOW, 1.0)
                        while budgets[lane] >= 1.0 and queues[lane]:
                            budgets[lane] -= 1.0
                            vehicle = queues[lane].pop(0)
                            vehicle.departed = t
                            served_total += 1
                            departures_this_tick += 1

            if on_tick is not None:
                on_tick(
                    TickState(
                        time=t,
                        phase=phase,
                        in_transition=in_transition,
                        phase_elapsed=green_elapsed,
                        queues={lane: len(queues[lane]) for lane in LANES},
                        departures=departures_this_tick,
                    )
                )

        return result
