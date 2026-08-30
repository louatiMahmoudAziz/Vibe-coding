"""Command-line interface.

    python -m traffic_sim.cli scenarios
    python -m traffic_sim.cli evaluate submissions/my_team/policy.py
    python -m traffic_sim.cli evaluate submissions/my_team/policy.py \
        --scenario side_street --seeds 7,8,9 --json
    python -m traffic_sim.cli watch submissions/my_team/policy.py \
        --scenario deploy_arena --seed 101 --every 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import LANES, Simulation, TickState
from .runner import evaluate_submission, load_policy_module
from .scenarios import DEFAULT_SEEDS, SCENARIOS


def _parse_seeds(raw: str):
    return tuple(int(part) for part in raw.split(",") if part.strip())


def cmd_scenarios(_args) -> int:
    print(f"{'name':<18} {'length':>7} {'~vehicles':>10}  description")
    print("-" * 100)
    for scenario in SCENARIOS.values():
        print(
            f"{scenario.name:<18} {scenario.horizon:>6}s "
            f"{scenario.expected_arrivals():>10.0f}  {scenario.description}"
        )
    return 0


def cmd_evaluate(args) -> int:
    seeds = _parse_seeds(args.seeds) if args.seeds else DEFAULT_SEEDS
    scenario_names = [args.scenario] if args.scenario else None
    if args.scenario and args.scenario not in SCENARIOS:
        print(f"error: unknown scenario {args.scenario!r}", file=sys.stderr)
        print(f"available: {', '.join(SCENARIOS)}", file=sys.stderr)
        return 2

    result = evaluate_submission(
        Path(args.policy), scenario_names, seeds, act=getattr(args, "act", None)
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if not result.load_error else 1

    print(f"\nTeam: {result.team}")
    print(f"Policy: {result.policy_path}")
    print(f"Seeds: {', '.join(map(str, seeds))}\n")
    if result.load_error:
        print(f"LOAD ERROR: {result.load_error}")
        return 1

    header = (
        f"{'scenario':<18} {'score':>7} {'served':>8} {'avg wait':>9} "
        f"{'p95':>6} {'starved':>8} {'switches':>9}"
    )
    print(header)
    print("-" * len(header))
    for scenario in result.scenario_scores:
        clean = [r for r in scenario.runs if r.error is None]
        served = (
            f"{100 * scenario.mean_served_fraction:.1f}%" if clean else "-"
        )
        p95 = (
            f"{sum(r.p95_wait for r in clean) / len(clean):.0f}s" if clean else "-"
        )
        switches = (
            f"{sum(r.switches for r in clean) / len(clean):.0f}" if clean else "-"
        )
        print(
            f"{scenario.scenario:<18} {scenario.mean_score:>7.2f} {served:>8} "
            f"{scenario.mean_avg_wait:>8.1f}s {p95:>6} "
            f"{scenario.total_starved:>8} {switches:>9}"
        )
        for run in scenario.runs:
            if run.error:
                print(f"    seed {run.seed}: ERROR - {run.error}")
    print("-" * len(header))
    print(f"{'TOTAL SCORE':<18} {result.total:>7.2f}   (0-100)")
    return 0


def cmd_watch(args) -> int:
    if args.scenario not in SCENARIOS:
        print(f"error: unknown scenario {args.scenario!r}", file=sys.stderr)
        return 2
    scenario = SCENARIOS[args.scenario]
    module = load_policy_module(Path(args.policy))
    policy = module.Policy()

    every = max(1, args.every)
    served = {"n": 0}

    def bar(n: int) -> str:
        return ("#" * min(n, 24)).ljust(24)

    def on_tick(state: TickState) -> None:
        served["n"] += state.departures
        if state.time % every != 0:
            return
        light = "YELLOW/RED" if state.in_transition else f"GREEN {state.phase_elapsed:>3}s"
        print(f"\nt={state.time:>5}s  phase={state.phase:<12} [{light}]  served={served['n']}")
        for lane in LANES:
            queue = state.queues[lane]
            print(f"   {lane:<11} |{bar(queue)}| {queue}")

    result = Simulation(scenario, args.seed).run(policy, on_tick=on_tick)
    from .metrics import score_run

    metrics = score_run(result)
    print(
        f"\nfinal: score={metrics.score:.2f} served={metrics.served}/{metrics.arrived} "
        f"avg_wait={metrics.avg_wait:.1f}s max_wait={metrics.max_wait}s "
        f"starved={metrics.starved} switches={metrics.switches}"
    )
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="traffic_sim", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("scenarios", help="list evaluation scenarios")

    evaluate = sub.add_parser("evaluate", help="score a policy file")
    evaluate.add_argument("policy", help="path to a policy.py")
    evaluate.add_argument("--scenario", help="run a single scenario")
    evaluate.add_argument("--seeds", help="comma-separated seeds (default: public seeds)")
    evaluate.add_argument("--json", action="store_true", help="emit JSON")
    evaluate.add_argument(
        "--act", choices=("act1", "act2", "deployment"),
        help="score only this act's traces (plus every earlier act's)",
    )

    watch = sub.add_parser("watch", help="replay one run with ASCII queue bars")
    watch.add_argument("policy", help="path to a policy.py")
    watch.add_argument("--scenario", default="pilot_morning")
    watch.add_argument("--seed", type=int, default=DEFAULT_SEEDS[0])
    watch.add_argument("--every", type=int, default=15, help="print every N sim-seconds")

    args = parser.parse_args(argv)
    if args.command == "scenarios":
        return cmd_scenarios(args)
    if args.command == "evaluate":
        return cmd_evaluate(args)
    if args.command == "watch":
        return cmd_watch(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
