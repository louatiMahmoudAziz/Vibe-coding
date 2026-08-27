# Traffic Flow Challenge - Leaderboard

Generated: `2026-08-27 17:01 UTC` &nbsp;|&nbsp; Seeds: `101, 202, 303` &nbsp;|&nbsp; Scenarios: 5 &nbsp;|&nbsp; Max score: 100

| # | Team | Total | Balanced Commute | North-South Rush Hour | Flash Crowd | Night Trickle | Gridlock Stress Test | Avg wait | Status |
|--:|:-----|------:|------:|------:|------:|------:|------:|---------:|:-------|
| 1 | Baseline: Max Pressure | **58.71** | 91.7 | 10.2 | 90.2 | 96.5 | 4.9 | 84.7s | ok |
| 2 | Baseline: Greedy Queue | **48.39** | 85.6 | 12.4 | 56.2 | 83.4 | 4.2 | 107.9s | ok |
| 3 | Baseline: Fixed Timer | **40.07** | 53.1 | 8.5 | 30.1 | 91.1 | 17.6 | 97.5s | ok |

Scoring per scenario: `60 x throughput + 40 x latency - starvation penalty` (see docs/SCORING.md). Total is the average across scenarios.
