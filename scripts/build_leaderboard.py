#!/usr/bin/env python3
"""Evaluate every submission and publish the leaderboard.

Usage:
    python scripts/build_leaderboard.py                # public seeds
    python scripts/build_leaderboard.py --seeds 7,8,9  # organizer (hidden) seeds
    python scripts/build_leaderboard.py --out results

Outputs into the output directory:
    results.json      full per-run metrics for every team
    leaderboard.md    Markdown standings (also nice in GitHub job summaries)
    leaderboard.html  polished standalone page to project on the workshop screen
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from traffic_sim.runner import discover_submissions, evaluate_submission  # noqa: E402
from traffic_sim.scenarios import DEFAULT_SEEDS, SCENARIOS  # noqa: E402


def rank_results(results):
    # Total score descending; mean average wait ascending breaks ties.
    return sorted(results, key=lambda r: (-r.total, r.mean_avg_wait, r.team.lower()))


def build_markdown(ranked, seeds, generated_at) -> str:
    scenario_names = list(SCENARIOS)
    lines = [
        "# Traffic Flow Challenge - Leaderboard",
        "",
        f"Generated: `{generated_at}` &nbsp;|&nbsp; Seeds: `{', '.join(map(str, seeds))}` "
        f"&nbsp;|&nbsp; Scenarios: {len(scenario_names)} &nbsp;|&nbsp; Max score: 100",
        "",
        "| # | Team | Total | "
        + " | ".join(SCENARIOS[n].title for n in scenario_names)
        + " | Avg wait | Status |",
        "|--:|:-----|------:|"
        + "".join("------:|" for _ in scenario_names)
        + "---------:|:-------|",
    ]
    for position, result in enumerate(ranked, start=1):
        per_scenario = {s.scenario: s for s in result.scenario_scores}
        cells = []
        for name in scenario_names:
            score = per_scenario.get(name)
            cells.append(f"{score.mean_score:.1f}" if score else "-")
        status = "error" if result.errors else "ok"
        total = f"**{result.total:.2f}**"
        lines.append(
            f"| {position} | {result.team} | {total} | "
            + " | ".join(cells)
            + f" | {result.mean_avg_wait:.1f}s | {status} |"
        )
    lines += [
        "",
        "Scoring per scenario: `60 x throughput + 40 x latency - starvation "
        "penalty` (see docs/SCORING.md). Total is the average across scenarios.",
    ]
    for result in ranked:
        if result.errors:
            lines.append("")
            lines.append(f"**{result.team} errors:**")
            for error in dict.fromkeys(result.errors):  # dedupe, keep order
                lines.append(f"- `{error}`")
    return "\n".join(lines) + "\n"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Traffic Flow Challenge - Leaderboard</title>
<style>
  :root {
    --bg: #0b1020;
    --panel: #131a30;
    --panel-2: #182142;
    --text: #e8ecf8;
    --muted: #8b93b0;
    --accent: #ffd166;
    --green: #2ee6a8;
    --amber: #ffb84d;
    --red: #ff6b81;
    --line: #232c4e;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
    background:
      radial-gradient(1100px 500px at 85% -10%, #1b2a5e 0%, transparent 60%),
      radial-gradient(900px 500px at -10% 110%, #10305e33 0%, transparent 60%),
      var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 40px 20px 64px;
  }
  .wrap { max-width: 1100px; margin: 0 auto; }
  header { display: flex; align-items: center; gap: 18px; margin-bottom: 8px; }
  .signal { display: flex; flex-direction: column; gap: 6px; background: #0a0e1c;
            border: 1px solid var(--line); border-radius: 12px; padding: 10px 8px; }
  .lamp { width: 16px; height: 16px; border-radius: 50%; opacity: 0.25; }
  .lamp.red { background: var(--red); }
  .lamp.amber { background: var(--amber); }
  .lamp.green { background: var(--green); opacity: 1;
                box-shadow: 0 0 14px 2px #2ee6a877; }
  h1 { font-size: 30px; margin: 0; letter-spacing: 0.3px; }
  h1 small { display: block; font-size: 14px; font-weight: 500; color: var(--muted); margin-top: 4px; }
  .meta { color: var(--muted); font-size: 13px; margin: 14px 2px 26px; }
  .meta code { color: var(--accent); background: #ffffff10; padding: 1px 7px; border-radius: 6px; }
  table { width: 100%; border-collapse: separate; border-spacing: 0;
          background: var(--panel); border: 1px solid var(--line);
          border-radius: 14px; overflow: hidden; }
  thead th { position: sticky; top: 0; background: var(--panel-2); color: var(--muted);
             font-size: 12px; text-transform: uppercase; letter-spacing: 0.8px;
             padding: 13px 12px; text-align: right; border-bottom: 1px solid var(--line); }
  thead th.team, thead th.rank { text-align: left; }
  tbody td { padding: 13px 12px; text-align: right; border-bottom: 1px solid var(--line);
             font-variant-numeric: tabular-nums; }
  tbody tr:last-child td { border-bottom: 0; }
  tbody tr:hover { background: #ffffff08; }
  td.team { text-align: left; font-weight: 600; }
  td.rank { text-align: left; }
  .badge { display: inline-flex; align-items: center; justify-content: center;
           min-width: 34px; height: 34px; border-radius: 10px; font-weight: 800;
           background: #ffffff12; color: var(--muted); }
  tr.p1 .badge { background: linear-gradient(160deg, #ffd166, #ff9a3d); color: #201200; }
  tr.p2 .badge { background: linear-gradient(160deg, #cfd8ea, #93a3c0); color: #101828; }
  tr.p3 .badge { background: linear-gradient(160deg, #e6a171, #b3663a); color: #21100a; }
  .total { font-size: 17px; font-weight: 800; color: var(--accent); }
  .cell { display: inline-flex; flex-direction: column; align-items: flex-end; gap: 4px; min-width: 74px; }
  .bar { width: 74px; height: 5px; border-radius: 3px; background: #ffffff14; overflow: hidden; }
  .bar span { display: block; height: 100%; border-radius: 3px; }
  .ok    { background: linear-gradient(90deg, #2ee6a8, #7bffcf); }
  .warn  { background: linear-gradient(90deg, #ffb84d, #ffd166); }
  .bad   { background: linear-gradient(90deg, #ff6b81, #ff9a8b); }
  .status-ok { color: var(--green); font-weight: 600; }
  .status-err { color: var(--red); font-weight: 600; }
  .errors { margin-top: 26px; background: var(--panel); border: 1px solid var(--line);
            border-radius: 14px; padding: 18px 22px; }
  .errors h2 { margin: 0 0 10px; font-size: 15px; color: var(--red); }
  .errors code { color: #ffc4cd; font-size: 12.5px; }
  .errors li { margin: 5px 0; color: var(--muted); }
  footer { margin-top: 26px; color: var(--muted); font-size: 12.5px; line-height: 1.6; }
  footer code { color: var(--accent); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="signal" aria-hidden="true">
      <div class="lamp red"></div><div class="lamp amber"></div><div class="lamp green"></div>
    </div>
    <h1>Traffic Flow Challenge
      <small>Optimize latency vs. throughput &mdash; adaptive signal control for a four-way intersection</small>
    </h1>
  </header>
  <p class="meta">Generated <code>__GENERATED__</code> &middot; evaluation seeds <code>__SEEDS__</code>
     &middot; __N_SCENARIOS__ scenarios &times; __N_SEEDS__ seeds per team &middot; max score <code>100</code></p>
  <table>
    <thead>
      <tr>
        <th class="rank">#</th>
        <th class="team">Team</th>
        <th>Total</th>
__SCENARIO_HEADERS__
        <th>Avg&nbsp;wait</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
__ROWS__
    </tbody>
  </table>
__ERRORS__
  <footer>
    Per-scenario score = <code>60 &times; throughput</code> + <code>40 &times; latency</code>
    &minus; <code>starvation penalty</code>; total is the average across scenarios.
    Bars show each scenario score out of 100.
    Rebuild with <code>python scripts/build_leaderboard.py</code>.
  </footer>
</div>
</body>
</html>
"""


def _bar_class(score: float) -> str:
    if score >= 70:
        return "ok"
    if score >= 40:
        return "warn"
    return "bad"


def build_html(ranked, seeds, generated_at) -> str:
    scenario_names = list(SCENARIOS)
    headers = "\n".join(
        f"        <th title=\"{html.escape(SCENARIOS[n].description)}\">"
        f"{html.escape(SCENARIOS[n].title)}</th>"
        for n in scenario_names
    )

    rows = []
    for position, result in enumerate(ranked, start=1):
        per_scenario = {s.scenario: s for s in result.scenario_scores}
        cells = []
        for name in scenario_names:
            score_obj = per_scenario.get(name)
            score = score_obj.mean_score if score_obj else 0.0
            cells.append(
                '        <td><span class="cell">'
                f"<b>{score:.1f}</b>"
                f'<span class="bar"><span class="{_bar_class(score)}" '
                f'style="width:{max(2, min(100, score)):.0f}%"></span></span>'
                "</span></td>"
            )
        status = (
            '<span class="status-err">error</span>'
            if result.errors
            else '<span class="status-ok">ok</span>'
        )
        podium = f" class=\"p{position}\"" if position <= 3 else ""
        rows.append(
            f"      <tr{podium}>\n"
            f'        <td class="rank"><span class="badge">{position}</span></td>\n'
            f'        <td class="team">{html.escape(result.team)}</td>\n'
            f'        <td class="total">{result.total:.2f}</td>\n'
            + "\n".join(cells)
            + f"\n        <td>{result.mean_avg_wait:.1f}s</td>\n"
            f"        <td>{status}</td>\n"
            f"      </tr>"
        )

    error_blocks = []
    for result in ranked:
        if result.errors:
            items = "".join(
                f"<li><code>{html.escape(e)}</code></li>"
                for e in dict.fromkeys(result.errors)
            )
            error_blocks.append(
                f"<h2>{html.escape(result.team)}</h2><ul>{items}</ul>"
            )
    errors_html = (
        f'  <div class="errors">{"".join(error_blocks)}</div>' if error_blocks else ""
    )

    page = HTML_TEMPLATE
    page = page.replace("__GENERATED__", html.escape(generated_at))
    page = page.replace("__SEEDS__", html.escape(", ".join(map(str, seeds))))
    page = page.replace("__N_SCENARIOS__", str(len(scenario_names)))
    page = page.replace("__N_SEEDS__", str(len(seeds)))
    page = page.replace("__SCENARIO_HEADERS__", headers)
    page = page.replace("__ROWS__", "\n".join(rows))
    page = page.replace("__ERRORS__", errors_html)
    return page


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submissions", default="submissions")
    parser.add_argument("--out", default="results")
    parser.add_argument("--seeds", help="comma-separated evaluation seeds")
    args = parser.parse_args()

    seeds = (
        tuple(int(s) for s in args.seeds.split(",") if s.strip())
        if args.seeds
        else DEFAULT_SEEDS
    )
    submissions_dir = REPO_ROOT / args.submissions
    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    policies = discover_submissions(submissions_dir)
    if not policies:
        print(f"no submissions found under {submissions_dir}", file=sys.stderr)
        return 1

    results = []
    for policy_path in policies:
        print(f"evaluating {policy_path} ...", flush=True)
        results.append(evaluate_submission(policy_path, seeds=seeds))

    ranked = rank_results(results)
    generated_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    (out_dir / "results.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "seeds": list(seeds),
                "scenarios": list(SCENARIOS),
                "standings": [r.to_dict() for r in ranked],
            },
            indent=2,
        )
        + "\n"
    )
    (out_dir / "leaderboard.md").write_text(build_markdown(ranked, seeds, generated_at))
    (out_dir / "leaderboard.html").write_text(build_html(ranked, seeds, generated_at))

    print()
    print(f"{'#':>3}  {'team':<28} {'total':>7}  status")
    print("-" * 52)
    for position, result in enumerate(ranked, start=1):
        status = "error" if result.errors else "ok"
        print(f"{position:>3}  {result.team:<28} {result.total:>7.2f}  {status}")
    print(f"\nwrote {out_dir}/results.json, leaderboard.md, leaderboard.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
