# Traffic Flow Challenge: Optimize Latency vs. Throughput

A workshop coding challenge. Teams use a coding agent to implement an
**adaptive traffic-light policy** for a four-way intersection, competing to
maximize vehicle throughput while minimizing waiting latency and preventing
starvation. Submissions are evaluated automatically against five realistic
traffic scenarios, and results are published to a live leaderboard.

```
            N_straight  N_left
                 |        |
                 v        v
            +----------------+
  W_straight |                | <- E_straight
  W_left ->  |   4-way        |
             |   intersection | <- E_left
            +----------------+
                 ^        ^
                 |        |
            S_left   S_straight
```

## The problem

You control the signal phases of one intersection. Every simulated second
your policy sees the queues and waiting times on all eight lanes and chooses
which of four phases should be green:

| Phase | Opens |
|-------|-------|
| `NS_STRAIGHT` | North + South through/right lanes |
| `NS_LEFT` | North + South protected left turns |
| `EW_STRAIGHT` | East + West through/right lanes |
| `EW_LEFT` | East + West protected left turns |

The engine enforces real-world signal safety for you: greens hold for at
least **6 s**, and every change costs **3 s yellow + 1 s all-red** during
which nobody moves, plus **2 s** of startup lost time when the new green
begins. Open lanes discharge one vehicle every 2 seconds. That is the whole
tension of the challenge: switching often keeps latency low, switching
rarely keeps throughput high, and ignoring a quiet lane starves it.

## Quickstart (participants)

Requires Python 3.10+ and nothing else — standard library only.

```bash
# 1. Create your team from the template
cp -r submissions/_template submissions/team_awesome
$EDITOR submissions/team_awesome/policy.py   # set TEAM_NAME, write decide()

# 2. Iterate locally
python -m traffic_sim.cli evaluate submissions/team_awesome/policy.py
python -m traffic_sim.cli watch submissions/team_awesome/policy.py --scenario rush_hour_ns

# 3. Self-check, then open a PR adding only your folder
python scripts/validate_submission.py submissions/team_awesome
```

CI evaluates every submission on each PR and publishes the standings; the
organizers regenerate the official leaderboard between rounds and re-run the
final ranking with **hidden seeds**, so overfitting the public seeds loses.

## The five evaluation scenarios

| Scenario | Length | What it stresses |
|----------|-------:|------------------|
| Balanced Commute | 15 min | Sanity: symmetric moderate demand |
| North-South Rush Hour | 15 min | Asymmetric green allocation without starving side streets |
| Flash Crowd | 20 min | Detecting and absorbing a sudden East-West surge |
| Night Trickle | 15 min | Latency: don't make a lone driver wait at an empty crossing |
| Gridlock Stress Test | 20 min | Throughput at ~95% capacity with a half-time demand flip |

Each scenario runs on 3 seeds; scores are averaged. List details with
`python -m traffic_sim.cli scenarios`.

## Scoring (0–100 per scenario)

```
score = 60 × (served / arrived)                 # throughput
      + 40 × max(0, 1 − avg_wait / 120 s)       # latency
      − min(30, 3 × vehicles_waiting_over_180s) # starvation penalty
```

Total = average across the five scenarios. Full details in
[docs/SCORING.md](docs/SCORING.md). Reference points on the public seeds:
the shipped baselines score **40** (fixed timer), **48** (greedy queue) and
**59** (max pressure); a well-tuned policy exceeds **80**.

## Leaderboard

```bash
python scripts/build_leaderboard.py            # evaluates all of submissions/
open results/leaderboard.html                  # project this on the big screen
```

Outputs `results/leaderboard.html` (styled standings page),
`results/leaderboard.md` (used in CI job summaries) and
`results/results.json` (full per-run metrics).

## Repository map

```
traffic_sim/            simulation engine, scenarios, scoring, CLI
  engine.py             intersection physics + signal safety interlocks
  scenarios.py          the five evaluation scenarios and public seeds
  metrics.py            scoring formulas
  runner.py             policy loading and evaluation harness
  cli.py                evaluate / watch / scenarios commands
submissions/            one folder per team (start from _template/)
scripts/
  validate_submission.py   participant self-check
  build_leaderboard.py     evaluate everyone, emit JSON + MD + HTML
tests/                  engine, scoring and harness tests (unittest)
docs/                   scoring spec, participant guide, organizer guide
.github/workflows/      automatic evaluation of submissions on every PR
```

## For organizers

Run-of-show, hidden-seed finals, and anti-cheat notes live in
[docs/ORGANIZER_GUIDE.md](docs/ORGANIZER_GUIDE.md). The short version:

```bash
make test                                       # harness self-test
make leaderboard                                # public standings between rounds
python scripts/build_leaderboard.py --seeds 9241,7717,3583   # secret finals
```
