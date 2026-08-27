# Participant Guide

You are writing the brain of a traffic light. This guide has everything you
need: the API, the physics, the tooling, and a strategy ladder to climb.

## Setup

```bash
cp -r submissions/_template submissions/<your_team>
```

Edit `submissions/<your_team>/policy.py`:

```python
TEAM_NAME = "Your Team Name"          # what the leaderboard displays

class Policy:
    def decide(self, obs) -> str:
        ...
        return "NS_STRAIGHT"          # the phase you want green now
```

`decide()` is called once per simulated second. Return one of
`"NS_STRAIGHT"`, `"NS_LEFT"`, `"EW_STRAIGHT"`, `"EW_LEFT"` (or the current
phase / `None` to hold). Illegal timing is impossible — the engine ignores
requests it can't honor — but an invalid *name* or an exception zeroes the
run, so don't get creative with return values.

A fresh `Policy()` is constructed for every run, so instance attributes are
safe per-run state (history, estimators, plans). There is no cross-run
state, and runs use different seeds anyway.

## The observation

| Field | Type | Meaning |
|-------|------|---------|
| `obs.time` | int | current second, starts at 0 |
| `obs.horizon` | int | scenario length in seconds |
| `obs.phase` | str | active (or most recent) green phase |
| `obs.phase_elapsed` | int | seconds the current green has been held |
| `obs.in_transition` | bool | yellow/all-red currently running |
| `obs.transition_remaining` | int | seconds left in the transition |
| `obs.can_switch` | bool | a switch request would take effect this tick |
| `obs.queues` | dict | lane → queued vehicles, e.g. `obs.queues["N_left"]` |
| `obs.oldest_wait` | dict | lane → seconds the front vehicle has waited |
| `obs.arrivals_total` | int | cumulative arrivals this run |
| `obs.served_total` | int | cumulative departures this run |
| `obs.min_green` / `obs.yellow` / `obs.all_red` | int | timing constants |
| `obs.phases` | tuple | the four phase names |

Lane names: `{N,E,S,W}_{straight,left}`. Phase→lanes mapping:
`NS_STRAIGHT` opens `N_straight` + `S_straight`, and so on.

## Physics cheat sheet

- Open lane: 1 vehicle per 2 s, after 2 s of startup lost time.
- Each phase opens exactly 2 lanes → max 1 veh/s while green.
- Every phase change: 3 s yellow + 1 s all-red + 2 s startup = **6 wasted
  seconds**. At ~0.7 veh/s demand, each switch costs ~4 car-service slots.
- Greens hold ≥ 6 s; requests during a transition are ignored (the target
  is latched when the yellow starts).

## Tooling

```bash
# full local evaluation, same as the leaderboard (public seeds)
python -m traffic_sim.cli evaluate submissions/<team>/policy.py

# one scenario, custom seeds, machine-readable
python -m traffic_sim.cli evaluate submissions/<team>/policy.py \
    --scenario gridlock_stress --seeds 1,2,3 --json

# watch your policy drive a run, with ASCII queue bars
python -m traffic_sim.cli watch submissions/<team>/policy.py \
    --scenario flash_crowd --every 10

# pre-flight check before opening your PR
python scripts/validate_submission.py submissions/<team>
```

## Strategy ladder

Each rung beats the previous one. How far you climb is up to you and your
coding agent.

1. **Fixed cycle** (~40 pts): rotate phases on fixed durations. Wastes
   green on empty lanes; dies in rush hour.
2. **Skip empty phases** (~45–50): never give green to a phase with no
   queue. Huge win at night.
3. **Greedy longest queue + hysteresis** (~50): serve the biggest queue,
   but only switch when the challenger clearly beats the incumbent —
   otherwise you burn 6 s per flip-flop.
4. **Pressure control with aging** (~55–60): score each phase by queue
   length weighted by waiting time; aging fixes starvation organically.
   Extend greens while they're discharging, cut them when flow stops.
5. **Demand-aware planning** (75+): estimate per-lane arrival rates from
   the queue history you've observed, allocate green time proportionally
   (long cycles under load to amortize switching, short cycles when quiet),
   serve queues down before leaving them, and keep a hard anti-starvation
   override. This is where the rush-hour and gridlock scenarios are won.

Things that separate the podium from the pack:

- **Switch discipline under load.** In gridlock, 100+ switches is an
  instant tell of a thrashing policy; the winners do ~50.
- **Drain before you leave.** Leaving 2 cars behind on a phase you just
  paid 6 s to open is throwing points away.
- **Watch the clock.** Near `obs.horizon`, an unserved queue is pure score
  loss — spend the last minutes clearing whatever is largest.
- **Don't overfit the public seeds.** Finals run on hidden seeds. If your
  constants only work on seed 101, you will fall on stage, in front of
  everyone.

## Rules

- Standard library only, one file, no I/O (disk, network, subprocess).
- 10 s wall-clock compute budget per run (~1200 `decide` calls) — generous
  unless you do something exotic.
- Don't modify anything outside your team folder. The harness and other
  teams' folders are protected by CI and organizer review.
