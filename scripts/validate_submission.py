#!/usr/bin/env python3
"""Self-check a submission before opening a PR.

Usage:
    python scripts/validate_submission.py submissions/your_team_name
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from traffic_sim.runner import (  # noqa: E402
    evaluate_run,
    load_policy_module,
    team_name_for,
)
from traffic_sim.scenarios import SCENARIOS  # noqa: E402

FORBIDDEN_IMPORTS = ("numpy", "pandas", "scipy", "requests", "torch", "sklearn")


def fail(msg: str) -> int:
    print(f"FAIL: {msg}")
    return 1


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    team_dir = Path(sys.argv[1])
    if not team_dir.is_dir():
        return fail(f"{team_dir} is not a directory")

    policy_path = team_dir / "policy.py"
    if not policy_path.is_file():
        return fail(f"{policy_path} not found - your policy must be policy.py")

    extra = [
        p.name
        for p in team_dir.iterdir()
        if p.name not in ("policy.py", "__pycache__") and not p.name.startswith(".")
    ]
    if extra:
        print(f"WARNING: extra files in {team_dir}: {extra} (only policy.py is evaluated)")

    source = policy_path.read_text()
    for module_name in FORBIDDEN_IMPORTS:
        if f"import {module_name}" in source:
            return fail(
                f"policy.py imports {module_name!r} - standard library only"
            )

    print(f"Loading {policy_path} ...")
    try:
        module = load_policy_module(policy_path)
    except Exception as exc:  # noqa: BLE001
        return fail(f"policy failed to import: {exc}")

    team = team_name_for(policy_path, module)
    if team == "Rename Me":
        return fail("set TEAM_NAME in policy.py (it is still 'Rename Me')")
    print(f"Team name: {team}")

    print("Running a smoke evaluation (pilot_morning, seed 101) ...")
    metrics = evaluate_run(module, SCENARIOS["pilot_morning"], 101)
    if metrics.error:
        return fail(f"policy crashed during simulation: {metrics.error}")

    print(
        f"OK: score {metrics.score:.2f}, served {metrics.served}/{metrics.arrived}, "
        f"avg wait {metrics.avg_wait:.1f}s"
    )
    print("\nSubmission looks valid. Full local evaluation:")
    print(f"  python -m traffic_sim.cli evaluate {policy_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
