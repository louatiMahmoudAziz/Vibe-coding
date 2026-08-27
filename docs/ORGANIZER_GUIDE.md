# Organizer Guide

How to run the Traffic Flow Challenge as a live workshop.

## Format that works well

| Segment | What happens |
|---------|--------------|
| Kickoff | Walk through README + the physics on one slide; demo `watch` mode with the fixed timer so everyone *sees* wasted green time |
| Sprint 1 | Teams get `evaluate` + `watch` running, beat the fixed timer (40 pts) |
| Checkpoint | Rebuild + project `results/leaderboard.html`; discuss why greedy beats fixed but collapses in gridlock |
| Sprint 2 | Teams chase the max-pressure baseline (59) and the 75+ frontier |
| Finals | Freeze submissions, re-run with **hidden seeds**, reveal standings |

Teams are encouraged to drive a coding agent: the repo is deliberately
self-describing (template docstring, participant guide, strategy ladder) so
an agent pointed at `submissions/_template/policy.py` has everything it
needs.

## Operating the leaderboard

```bash
# between rounds (public seeds), then project results/leaderboard.html
python scripts/build_leaderboard.py

# finals: your own seeds, kept secret until the reveal
python scripts/build_leaderboard.py --seeds 9241,7717,3583 --out results_final
```

- The HTML page is fully standalone — open it in any browser, press F11.
- Every rebuild re-evaluates all of `submissions/` from scratch; a full
  board of ~20 teams takes a few seconds.
- `results/results.json` has per-run metrics if a team disputes a score.

## Submission flow

Two options, pick per venue:

1. **Pull requests (recommended).** Teams PR their folder; the GitHub
   Actions workflow runs the harness tests, validates every submission and
   posts the standings into the job summary. Merge, rebuild, project.
2. **Shared drive / USB sneakernet.** Drop each team's folder into
   `submissions/` and rebuild. Nothing else to configure.

## Fair play

- The evaluation imports participant code in-process. For a friendly
  workshop that's fine; review PR diffs before merging (CI restricting
  changes to `submissions/**` paths + branch protection on everything else
  covers most mischief).
- `validate_submission.py` rejects obvious rule breaks (third-party
  imports, missing TEAM_NAME); the runner converts crashes, invalid phases
  and blown compute budgets into zero-score runs with the error displayed
  on the leaderboard rather than taking the harness down.
- Hidden seeds are your main anti-overfitting tool. Pick any integers,
  keep them secret until the reveal, and announce up front that finals use
  them — it changes how teams engineer.

## Tuning difficulty

All knobs live in two files, and the test suite pins the invariants:

- `traffic_sim/scenarios.py` — arrival rates, horizons, seeds, weights.
  Raising `gridlock_stress` rates by ~10% makes the top of the board brutal;
  lowering `rush_hour_ns` to 0.18 makes it friendly for shorter workshops.
- `traffic_sim/metrics.py` — points split (60/40), the 120 s latency
  anchor, the 180 s starvation threshold and 3-point unit penalty.

After changing anything, run `make test` and rebuild the leaderboard to
re-baseline the demo teams. Reference calibration on public seeds: fixed
timer ≈ 40, greedy ≈ 48, max pressure ≈ 59, tuned expert policy ≈ 85.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Team shows `error` status on the board | The exact exception is printed under the table (and in `results.json`); it's their code, not yours |
| Two teams claim the same name | `TEAM_NAME` is display-only; ranking is per folder. Ask one to rename |
| A run "hangs" | The 10 s per-run budget aborts it and scores 0; check the error column |
| Scores differ between machines | They shouldn't — the sim is seed-deterministic and dependency-free. Verify both sides are on the same commit and seeds |
