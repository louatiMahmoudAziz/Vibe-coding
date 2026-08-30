"""Metrics and scoring.

Score per run (0-100):

    throughput_pts  = 60 * served / arrived
    latency_pts     = 40 * max(0, 1 - avg_wait / 120)
    starvation_pen  = min(30, 3 * starved_vehicles)      # wait > 180 s
    score           = max(0, throughput_pts + latency_pts - starvation_pen)

Vehicles still queued when the clock runs out count as unserved and their
wait is censored at the horizon, so abandoning a queue hurts both terms.

A submission's scenario score is the mean over the evaluation seeds, and the
total score is the weighted mean over scenarios (all weights are 1.0 by
default, so it is a plain average).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .engine import RunResult

STARVATION_THRESHOLD = 180   # seconds of waiting that counts as starved
LATENCY_HALFCOURT = 120      # avg wait (s) at which latency points hit zero
THROUGHPUT_POINTS = 60.0
LATENCY_POINTS = 40.0
STARVATION_UNIT_PENALTY = 3.0
STARVATION_PENALTY_CAP = 30.0



# --------------------------------------------------------------------------- #
# Requirements
#
# The participant reads these, not the score. Each is a named pass/fail thing
# the client asked for, and failing one ranks you below everyone who passed --
# whatever your averages look like. That ordering is the whole point: an
# optimised system can still be an unacceptable one, and the leaderboard has to
# be able to say so.
#
# THRESHOLDS ARE PROVISIONAL. 
# MAX_WAIT_LIMIT is grounded: across twelve AI-written controllers, ones that
# weighed waiting at all landed near 100 s on these traces while one that
# ignored it entirely sat at ~350 s, so 140 s sits in that gap -- normal cyclic
# waiting passes, real starvation fails. THROUGHPUT_FLOOR and AVG_WAIT_LIMIT are
# educated guesses. Run scripts/calibrate_model.py against the model you will
# actually ship, look at the distribution it prints, and set these so roughly
# 70% pass Act 1 and 30% pass Act 2. Thresholds are a dial for drama, not a
# fact about traffic.
# --------------------------------------------------------------------------- #

THROUGHPUT_FLOOR = 0.85     # fraction of arrivals that must clear
AVG_WAIT_LIMIT = 45.0       # seconds, mean over every vehicle
MAX_WAIT_LIMIT = 140        # seconds, the single worst wait anybody had

# Which requirements are live in which act. Act 1 deliberately does not include
# the starvation rule -- the client has not asked for it yet, and discovering it
# in Act 2 is the lesson.
ACT_REQUIREMENTS: Dict[str, Tuple[str, ...]] = {
    "act1": ("throughput", "avg_wait"),
    "act2": ("throughput", "avg_wait", "max_wait"),
    "deployment": ("throughput", "avg_wait", "max_wait"),
}


@dataclass
class Requirement:
    key: str
    label: str          # what the participant reads
    detail: str         # the threshold, in words
    actual: str         # what they got
    passed: bool

    def to_dict(self) -> Dict:
        return {
            "key": self.key, "label": self.label, "detail": self.detail,
            "actual": self.actual, "passed": self.passed,
        }


def evaluate_requirements(
    served_fraction: float, avg_wait: float, max_wait: int, act: str = "act2"
) -> List[Requirement]:
    """Turn raw numbers into the three things the client actually asked for."""
    live = ACT_REQUIREMENTS.get(act, ACT_REQUIREMENTS["act2"])
    checks = {
        "throughput": Requirement(
            "throughput", "Traffic keeps moving",
            f"at least {THROUGHPUT_FLOOR:.0%} of vehicles clear",
            f"{served_fraction:.1%}", served_fraction >= THROUGHPUT_FLOOR,
        ),
        "avg_wait": Requirement(
            "avg_wait", "The typical trip is reasonable",
            f"average wait at most {AVG_WAIT_LIMIT:.0f}s",
            f"{avg_wait:.0f}s", avg_wait <= AVG_WAIT_LIMIT,
        ),
        "max_wait": Requirement(
            "max_wait", "Nobody is stranded",
            f"no vehicle waits over {MAX_WAIT_LIMIT}s",
            f"{max_wait}s", max_wait <= MAX_WAIT_LIMIT,
        ),
    }
    return [checks[k] for k in live if k in checks]


def rank_key(passed_all: bool, avg_wait: float, p95_wait: float):
    """Sort key for the leaderboard. Lower is better, passers first.

    Among controllers that satisfy every requirement, order by a composite of
    typical and tail experience -- a great average that hides a bad tail should
    not beat a controller that is good for everybody. The gates already stop
    pathological behaviour, so the composite is only ordering survivors.
    """
    return (0 if passed_all else 1, avg_wait + 0.3 * p95_wait)


@dataclass
class RunMetrics:
    scenario: str
    seed: int
    arrived: int = 0
    served: int = 0
    avg_wait: float = 0.0
    p95_wait: float = 0.0
    max_wait: int = 0
    starved: int = 0
    switches: int = 0
    throughput_pts: float = 0.0
    latency_pts: float = 0.0
    starvation_penalty: float = 0.0
    score: float = 0.0
    error: Optional[str] = None
    requirements: List[Requirement] = field(default_factory=list)
    passed_all: bool = False

    def to_dict(self) -> Dict:
        return {
            "scenario": self.scenario,
            "seed": self.seed,
            "arrived": self.arrived,
            "served": self.served,
            "avg_wait": round(self.avg_wait, 2),
            "p95_wait": round(self.p95_wait, 2),
            "max_wait": self.max_wait,
            "starved": self.starved,
            "switches": self.switches,
            "throughput_pts": round(self.throughput_pts, 2),
            "latency_pts": round(self.latency_pts, 2),
            "starvation_penalty": round(self.starvation_penalty, 2),
            "score": round(self.score, 2),
            "error": self.error,
            "requirements": [r.to_dict() for r in self.requirements],
            "passed_all": self.passed_all,
        }


def score_run(result: RunResult, act: str = "act2") -> RunMetrics:
    metrics = RunMetrics(scenario=result.scenario_name, seed=result.seed)
    metrics.switches = result.switches
    vehicles = result.vehicles
    metrics.arrived = len(vehicles)

    if metrics.arrived == 0:
        # Degenerate case: nothing to do, full marks.
        metrics.throughput_pts = THROUGHPUT_POINTS
        metrics.latency_pts = LATENCY_POINTS
        metrics.score = THROUGHPUT_POINTS + LATENCY_POINTS
        metrics.requirements = evaluate_requirements(1.0, 0.0, 0, act)
        metrics.passed_all = True
        return metrics

    waits: List[int] = sorted(v.wait(result.horizon) for v in vehicles)
    metrics.served = sum(1 for v in vehicles if v.served)
    metrics.avg_wait = sum(waits) / len(waits)
    metrics.p95_wait = float(waits[int(0.95 * (len(waits) - 1))])
    metrics.max_wait = waits[-1]
    metrics.starved = sum(1 for w in waits if w > STARVATION_THRESHOLD)

    metrics.throughput_pts = THROUGHPUT_POINTS * metrics.served / metrics.arrived
    metrics.latency_pts = LATENCY_POINTS * max(
        0.0, 1.0 - metrics.avg_wait / LATENCY_HALFCOURT
    )
    metrics.starvation_penalty = min(
        STARVATION_PENALTY_CAP, STARVATION_UNIT_PENALTY * metrics.starved
    )
    metrics.score = max(
        0.0,
        metrics.throughput_pts + metrics.latency_pts - metrics.starvation_penalty,
    )

    metrics.requirements = evaluate_requirements(
        metrics.served / metrics.arrived, metrics.avg_wait, metrics.max_wait, act
    )
    metrics.passed_all = all(r.passed for r in metrics.requirements)
    return metrics


def failed_run(scenario: str, seed: int, error: str) -> RunMetrics:
    return RunMetrics(scenario=scenario, seed=seed, score=0.0, error=error)


@dataclass
class ScenarioScore:
    scenario: str
    weight: float
    runs: List[RunMetrics] = field(default_factory=list)

    @property
    def mean_score(self) -> float:
        if not self.runs:
            return 0.0
        return sum(r.score for r in self.runs) / len(self.runs)

    @property
    def mean_avg_wait(self) -> float:
        clean = [r for r in self.runs if r.error is None]
        if not clean:
            return 0.0
        return sum(r.avg_wait for r in clean) / len(clean)

    @property
    def mean_served_fraction(self) -> float:
        clean = [r for r in self.runs if r.error is None and r.arrived > 0]
        if not clean:
            return 0.0
        return sum(r.served / r.arrived for r in clean) / len(clean)

    @property
    def total_starved(self) -> int:
        return sum(r.starved for r in self.runs)

    @property
    def errors(self) -> List[str]:
        return [r.error for r in self.runs if r.error]

    def to_dict(self) -> Dict:
        return {
            "scenario": self.scenario,
            "weight": self.weight,
            "mean_score": round(self.mean_score, 2),
            "mean_avg_wait": round(self.mean_avg_wait, 2),
            "mean_served_fraction": round(self.mean_served_fraction, 4),
            "total_starved": self.total_starved,
            "runs": [r.to_dict() for r in self.runs],
        }


def total_score(scenario_scores: List[ScenarioScore]) -> float:
    if not scenario_scores:
        return 0.0
    weight_sum = sum(s.weight for s in scenario_scores)
    if weight_sum == 0:
        return 0.0
    return sum(s.mean_score * s.weight for s in scenario_scores) / weight_sum
