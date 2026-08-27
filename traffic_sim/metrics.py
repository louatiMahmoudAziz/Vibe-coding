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
from typing import Dict, List, Optional

from .engine import RunResult

STARVATION_THRESHOLD = 180   # seconds of waiting that counts as starved
LATENCY_HALFCOURT = 120      # avg wait (s) at which latency points hit zero
THROUGHPUT_POINTS = 60.0
LATENCY_POINTS = 40.0
STARVATION_UNIT_PENALTY = 3.0
STARVATION_PENALTY_CAP = 30.0


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
        }


def score_run(result: RunResult) -> RunMetrics:
    metrics = RunMetrics(scenario=result.scenario_name, seed=result.seed)
    metrics.switches = result.switches
    vehicles = result.vehicles
    metrics.arrived = len(vehicles)

    if metrics.arrived == 0:
        # Degenerate case: nothing to do, full marks.
        metrics.throughput_pts = THROUGHPUT_POINTS
        metrics.latency_pts = LATENCY_POINTS
        metrics.score = THROUGHPUT_POINTS + LATENCY_POINTS
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
