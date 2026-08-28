#!/usr/bin/env python3
"""Is this model the right difficulty for the challenge?

Runs two arms through the real gateway, scores them with the real evaluator,
and reports whether the model discriminates between lazy and careful direction.

    python3 scripts/calibrate_model.py --model gemini-2.5-flash-lite
    python3 scripts/calibrate_model.py --model gemini-2.5-flash --n 8

Needs GEMINI_API_KEY (or VCC_SECRET_ID) in the environment, same as the server.

What the numbers mean
---------------------
crash rate      generations that would not load at all. Above ~15% and Round 1
                becomes a debugging exercise instead of feeling like magic.
naive pass      lazy prompts that clear the bar. Your own viability rule:
                0-2 of 10 is an excellent challenge, 8+ means redesign.
directed pass   careful prompts that clear the bar. If this is not clearly
                higher than naive pass, the model is too weak and the whole
                thesis collapses - direction has to be worth something.
spread          naive score range. A huge spread means the leaderboard sorts
                on sampling luck rather than judgment.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from traffic_sim.runner import evaluate_submission  # noqa: E402
from webboard import gateway  # noqa: E402

NAIVE_PROMPTS = [
    "Implement an adaptive traffic controller.",
    "Write a smart traffic light policy. Make it adaptive.",
    "Build me a controller that keeps traffic moving.",
    "Make the intersection efficient. Handle busy periods.",
    "Write a policy that decides which phase should be green.",
    "Control the lights so cars don't wait too long.",
    "Give me a good adaptive signal controller.",
    "Make it smart - serve whichever direction needs it most.",
    "Write the traffic controller. Keep it simple but effective.",
    "Implement a policy that minimises waiting time.",
]

DIRECTED_PROMPT = """\
Treat this as a scheduling problem with competing objectives and resolve the
conflict explicitly.

HARD CONSTRAINT: no lane may wait longer than 90 seconds, including a lane
with a single vehicle while another axis is saturated and never drains. This
ceiling must take strict precedence over everything below.

Then, subject to that:
- every phase change burns yellow + all-red + startup lost time, so require a
  real pressure advantage before switching, and do not oscillate when two
  phases are near-equal
- never hold green on an empty phase while another has vehicles waiting
- the four phases are served independently; protected left lanes starve first
  because their queues are small, so weight waiting time, not just queue length
- minimise average wait only after all of the above hold

The trap: the anti-oscillation margin is exactly what causes starvation. A
margin large enough to stop thrashing will also stop a two-car left lane from
ever beating a busy through movement. Make the starvation ceiling override the
margin, not the other way round.
"""

CLIENT_BRIEF = """\
Our smart intersection is launching downtown. Drivers say traffic feels slow,
especially at busy times. Keep traffic moving efficiently. Changing the signal
direction costs several seconds of lost capacity.

"""


def run_arm(label, prompts, tmpdir, db_path, pid, verbose):
    rows = []
    for i, prompt in enumerate(prompts, 1):
        tag = f"{label}-{i}"
        try:
            gen = gateway.generate(db_path, pid, CLIENT_BRIEF + prompt)
        except gateway.GatewayError as exc:
            print(f"  {tag:<12} GATEWAY FAIL: {exc}")
            rows.append({"tag": tag, "crashed": True, "score": 0.0, "max_wait": None})
            continue

        path = Path(tmpdir) / f"{tag}.py"
        path.write_text(gen.code, encoding="utf-8")
        result = evaluate_submission(path)

        if result.load_error or result.errors:
            print(f"  {tag:<12} DID NOT RUN: {(result.load_error or result.errors[0])[:60]}")
            rows.append({"tag": tag, "crashed": True, "score": 0.0, "max_wait": None})
            continue

        worst = max(
            (r.max_wait for s in result.scenario_scores for r in s.runs if r.error is None),
            default=0,
        )
        starved = sum(s.total_starved for s in result.scenario_scores)
        rows.append({
            "tag": tag, "crashed": False, "score": result.total,
            "max_wait": worst, "starved": starved,
            "retried": gen.attempts > 1, "tokens": gen.charged,
        })
        print(f"  {tag:<12} score {result.total:6.2f}   worst wait {worst:>5}s   "
              f"starved {starved:>5}   {'(retried)' if gen.attempts > 1 else ''}")
        if verbose:
            print("      " + gen.code.replace("\n", "\n      ")[:600])
    return rows


def summarise(label, rows, bar):
    live = [r for r in rows if not r["crashed"]]
    crashes = len(rows) - len(live)
    passed = [r for r in live if r["max_wait"] is not None and r["max_wait"] <= bar]
    scores = [r["score"] for r in live]
    print(f"\n{label}")
    print(f"  crashed / total : {crashes}/{len(rows)}")
    print(f"  passed (<= {bar}s): {len(passed)}/{len(rows)}")
    if scores:
        print(f"  score  median   : {statistics.median(scores):.2f}")
        print(f"  score  range    : {min(scores):.2f} - {max(scores):.2f}")
        if len(scores) > 1:
            print(f"  score  stdev    : {statistics.pstdev(scores):.2f}")
    return len(passed), len(rows), crashes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=gateway.MODEL)
    ap.add_argument("--n", type=int, default=len(NAIVE_PROMPTS),
                    help="naive samples (directed arm uses n//2, min 3)")
    ap.add_argument("--bar", type=int, default=90,
                    help="max acceptable wait in seconds")
    ap.add_argument("--verbose", action="store_true", help="print generated code")
    args = ap.parse_args()

    gateway.MODEL = args.model
    print(f"model       : {gateway.MODEL}")
    print(f"temperature : {gateway.TEMPERATURE}")
    print(f"key source  : {gateway.key_source()}\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "calib.sqlite3"
        from webboard import db as _db
        _db.init(db_path)
        gateway.ensure_schema(db_path)
        pid = _db.create_participant(db_path, "calibration", "calibration-pw")["id"]
        gateway.grant_budget(db_path, pid, 5_000_000)   # not the thing under test

        n_naive = max(1, min(args.n, len(NAIVE_PROMPTS)))
        n_directed = max(3, n_naive // 2)

        print(f"ARM A - lazy prompting ({n_naive} samples)")
        naive = run_arm("naive", NAIVE_PROMPTS[:n_naive], tmpdir, db_path, pid, args.verbose)

        print(f"\nARM B - directed prompting ({n_directed} samples)")
        directed = run_arm(
            "directed", [DIRECTED_PROMPT] * n_directed, tmpdir, db_path, pid, args.verbose
        )

        print("\n" + "=" * 66)
        n_pass, n_tot, n_crash = summarise("ARM A - lazy", naive, args.bar)
        d_pass, d_tot, d_crash = summarise("ARM B - directed", directed, args.bar)

        spent = gateway.budget_state(db_path, pid)["spent"]
        print("\n" + "=" * 66)
        print("VERDICT")
        print("=" * 66)
        crash_rate = (n_crash + d_crash) / max(1, n_tot + d_tot)
        naive_rate = n_pass / max(1, n_tot)
        dir_rate = d_pass / max(1, d_tot)

        ok = True
        if crash_rate > 0.15:
            print(f"  FAIL  crash rate {crash_rate:.0%} - Round 1 will feel broken,")
            print("        not magical. The model is too weak to carry the opening beat.")
            ok = False
        else:
            print(f"  ok    crash rate {crash_rate:.0%}")

        if dir_rate < 0.6:
            print(f"  FAIL  directed prompts pass only {dir_rate:.0%}. Careful direction")
            print("        earns nothing, so the challenge measures luck. Use a stronger model.")
            ok = False
        else:
            print(f"  ok    directed prompts pass {dir_rate:.0%}")

        if naive_rate > 0.5:
            print(f"  FAIL  lazy prompts pass {naive_rate:.0%} - the trap does not trap.")
            print("        Use a stronger scenario or a weaker model.")
            ok = False
        else:
            print(f"  ok    lazy prompts pass {naive_rate:.0%}")

        gap = dir_rate - naive_rate
        print(f"\n  discriminator gap: {gap:+.0%}  (directed {dir_rate:.0%} - lazy {naive_rate:.0%})")
        print(f"  tokens spent     : {spent:,}")
        print(f"\n  {'USE THIS MODEL' if ok and gap >= 0.4 else 'DO NOT SHIP THIS CONFIGURATION'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
