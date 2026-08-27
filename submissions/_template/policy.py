"""Traffic Flow Challenge - starter template.

Copy this folder to submissions/<your_team_name>/ and start hacking.

Your job: implement `Policy.decide(obs)`. It is called once per simulated
second and must return the phase you want to be green, one of:

    "NS_STRAIGHT"   -> opens N_straight and S_straight
    "NS_LEFT"       -> opens N_left and S_left
    "EW_STRAIGHT"   -> opens E_straight and W_straight
    "EW_LEFT"       -> opens E_left and W_left

Returning the current phase (or None) keeps the light as it is. The engine
enforces all safety rules for you: a green holds at least `obs.min_green`
seconds, and every change costs `obs.yellow + obs.all_red` seconds of dead
time during which nobody moves. Requests made while a switch is impossible
are simply ignored, so you may return your desired phase every tick.

What you can see each tick (the `obs` object):

    obs.time                 current second (int)
    obs.horizon              total scenario length in seconds
    obs.phase                the active (or most recent) green phase
    obs.phase_elapsed        seconds the current green has been held
    obs.in_transition        True while yellow / all-red is running
    obs.can_switch           True if a switch request would take effect now
    obs.queues               dict lane -> queued vehicles, e.g. obs.queues["N_left"]
    obs.oldest_wait          dict lane -> seconds the FRONT vehicle has waited
    obs.arrivals_total       vehicles that have arrived so far
    obs.served_total         vehicles that have crossed so far
    obs.phases               tuple of the four phase names

Useful physics constants:
    - an open lane serves 1 vehicle per 2 seconds, after 2 startup seconds
    - each phase opens exactly 2 lanes
    - a phase change wastes 4 seconds (yellow + all-red) + 2 startup seconds

Scoring (per scenario, 0-100):
    60 * (served / arrived)                      throughput
  + 40 * max(0, 1 - avg_wait / 120)              latency
  -  3 * (# vehicles waiting > 180 s), cap 30    starvation penalty

Rules:
    - Python 3 standard library only, single file, no disk/network access.
    - Your Policy is re-instantiated for every run; you may keep any state
      you like on `self` within a run.
    - Total compute budget: 10 s wall-clock per run (~1200 decide calls).
"""

TEAM_NAME = "Rename Me"


class Policy:
    def __init__(self):
        # Per-run state lives here (the class is re-created for every run).
        pass

    def decide(self, obs) -> str:
        # --- replace this naive round-robin with something smart ---------
        # It rotates through all four phases on a fixed 20-second cycle,
        # even when the lanes it opens are empty. You can do much better.
        index = (obs.time // 20) % len(obs.phases)
        return obs.phases[index]
