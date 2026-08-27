"""Load participant policies and evaluate them across scenarios and seeds."""

from __future__ import annotations

import importlib.util
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .engine import PolicyError, Simulation
from .metrics import (
    RunMetrics,
    ScenarioScore,
    failed_run,
    score_run,
    total_score,
)
from .scenarios import DEFAULT_SEEDS, SCENARIOS, Scenario


@dataclass
class SubmissionResult:
    team: str
    policy_path: str
    scenario_scores: List[ScenarioScore] = field(default_factory=list)
    load_error: Optional[str] = None

    @property
    def total(self) -> float:
        if self.load_error:
            return 0.0
        return total_score(self.scenario_scores)

    @property
    def mean_avg_wait(self) -> float:
        clean = [s.mean_avg_wait for s in self.scenario_scores if s.runs]
        return sum(clean) / len(clean) if clean else 0.0

    @property
    def errors(self) -> List[str]:
        errors = [self.load_error] if self.load_error else []
        for scenario in self.scenario_scores:
            errors.extend(scenario.errors)
        return errors

    def to_dict(self) -> Dict:
        return {
            "team": self.team,
            "policy_path": self.policy_path,
            "total_score": round(self.total, 2),
            "mean_avg_wait": round(self.mean_avg_wait, 2),
            "load_error": self.load_error,
            "scenarios": [s.to_dict() for s in self.scenario_scores],
        }


_module_counter = 0


def load_policy_module(policy_path: Path):
    """Import a policy file under a unique module name."""
    global _module_counter
    _module_counter += 1
    name = f"_traffic_policy_{_module_counter}_{policy_path.stem}"
    spec = importlib.util.spec_from_file_location(name, policy_path)
    if spec is None or spec.loader is None:
        raise PolicyError(f"cannot import {policy_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "Policy"):
        raise PolicyError(f"{policy_path} does not define a `Policy` class")
    policy_cls = module.Policy
    if not callable(getattr(policy_cls, "decide", None)):
        raise PolicyError(f"{policy_path}: `Policy` has no callable `decide` method")
    return module


def team_name_for(policy_path: Path, module=None) -> str:
    if module is not None:
        name = getattr(module, "TEAM_NAME", None)
        if isinstance(name, str) and name.strip():
            return name.strip()
    parent = policy_path.parent.name
    return parent if parent not in ("", ".") else policy_path.stem


def _short_error(exc: BaseException) -> str:
    if isinstance(exc, PolicyError):
        return str(exc)
    last = traceback.format_exception_only(type(exc), exc)[-1].strip()
    tb = traceback.extract_tb(exc.__traceback__)
    where = ""
    for frame in reversed(tb):
        if "_traffic_policy_" in frame.filename or frame.filename.endswith("policy.py"):
            where = f" (policy.py line {frame.lineno})"
            break
    return f"{last}{where}"


def evaluate_run(module, scenario: Scenario, seed: int) -> RunMetrics:
    """Run one (scenario, seed) with a fresh policy instance."""
    try:
        policy = module.Policy()
        result = Simulation(scenario, seed).run(policy)
        return score_run(result)
    except Exception as exc:  # noqa: BLE001 - participant code can fail any way
        return failed_run(scenario.name, seed, _short_error(exc))


def evaluate_submission(
    policy_path: Path,
    scenario_names: Optional[Sequence[str]] = None,
    seeds: Optional[Iterable[int]] = None,
    team: Optional[str] = None,
) -> SubmissionResult:
    policy_path = Path(policy_path)
    seeds = tuple(seeds) if seeds else DEFAULT_SEEDS
    names = list(scenario_names) if scenario_names else list(SCENARIOS)

    try:
        module = load_policy_module(policy_path)
    except Exception as exc:  # noqa: BLE001
        return SubmissionResult(
            team=team or team_name_for(policy_path),
            policy_path=str(policy_path),
            load_error=_short_error(exc),
        )

    result = SubmissionResult(
        team=team or team_name_for(policy_path, module),
        policy_path=str(policy_path),
    )
    for name in names:
        scenario = SCENARIOS[name]
        scenario_score = ScenarioScore(scenario=name, weight=scenario.weight)
        for seed in seeds:
            scenario_score.runs.append(evaluate_run(module, scenario, seed))
        result.scenario_scores.append(scenario_score)
    return result


def discover_submissions(submissions_dir: Path) -> List[Path]:
    """Find every submissions/<team>/policy.py, skipping the template."""
    found = []
    for path in sorted(Path(submissions_dir).iterdir()):
        if not path.is_dir() or path.name.startswith(("_", ".")):
            continue
        policy = path / "policy.py"
        if policy.is_file():
            found.append(policy)
    return found
