# Scoring Specification

This document is the authoritative description of how submissions are
ranked. The implementation lives in `traffic_sim/metrics.py`; if the two
ever disagree, the code wins and the docs get fixed.

## Per-run metrics

One *run* is one (scenario, seed) simulation. For every vehicle the engine
records its arrival second and, if it crossed, its departure second.

| Metric | Definition |
|--------|------------|
| `arrived` | vehicles generated during the run |
| `served` | vehicles that crossed before the horizon |
| `wait` (per vehicle) | `departure − arrival`; vehicles still queued at the end are **censored at the horizon**: `horizon − arrival` |
| `avg_wait` | mean wait over **all** arrived vehicles (served + censored) |
| `p95_wait`, `max_wait` | diagnostics only, not scored |
| `starved` | vehicles whose wait exceeds **180 s** |
| `switches` | phase changes requested and executed |

Censoring at the horizon means abandoning a queue hurts twice: those
vehicles are unserved (throughput) *and* they drag `avg_wait` up (latency).

## Per-run score (0–100)

```
throughput_pts = 60 × served / arrived
latency_pts    = 40 × max(0, 1 − avg_wait / 120)
starvation_pen = min(30, 3 × starved)
score          = max(0, throughput_pts + latency_pts − starvation_pen)
```

Design intent:

- **Throughput dominates (60 pts)** — a signal plan that doesn't move cars
  is worthless, no matter how "fair" it is.
- **Latency is worth fighting for (40 pts)** — every 3 s of average wait
  costs one point; at 120 s average wait the latency points are gone.
- **Starvation is punished, capped (30 pts)** — the cap keeps one
  pathological lane from zeroing an otherwise strong run, but 10+ starved
  vehicles wipe out a third of the maximum score.
- If a run raises an exception, returns an invalid phase, or exceeds the
  10 s wall-clock compute budget, that run scores **0** and the error is
  shown on the leaderboard.
- Degenerate runs with zero arrivals score 100 by definition.

## Aggregation

```
scenario_score = mean over seeds of run scores
total_score    = weighted mean over scenarios (all weights 1.0)
```

Ties on `total_score` are broken by lower mean average wait, then by team
name for full determinism.

## Seeds

- **Public seeds** `101, 202, 303` are used for local development, CI, and
  the live leaderboard shown during the workshop.
- **Hidden seeds** are chosen by the organizers and revealed only when the
  final ranking is announced (`--seeds` flag on `build_leaderboard.py`).
  The scenario definitions do not change — only the random arrival draws —
  so robust policies transfer and seed-overfitted ones regress publicly.

## Signal physics (fixed, engine-enforced)

| Constant | Value | Meaning |
|----------|------:|---------|
| `MIN_GREEN` | 6 s | a green cannot change earlier |
| `YELLOW` | 3 s | dead time on every change |
| `ALL_RED` | 1 s | dead time on every change |
| `STARTUP_LOST` | 2 s | green time before the first car moves |
| `SATURATION_FLOW` | 0.5 veh/s/lane | one car every 2 s per open lane |

A full phase change therefore costs 6 effective seconds (4 dead + 2
startup). With two lanes per phase, the intersection's ceiling is 1.0 veh/s
while green — sustained total demand of ~0.7 veh/s (rush hour, gridlock)
leaves almost no green time to waste.
