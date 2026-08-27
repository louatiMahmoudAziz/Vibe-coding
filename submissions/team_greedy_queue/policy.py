"""Demo baseline: greedy longest-queue-first with hysteresis.

Every time a switch is possible, serve the phase with the most queued
vehicles - but only if it beats the current phase by a clear margin, so the
light does not thrash. A simple anti-starvation override protects lanes
whose front vehicle has waited too long.
"""

TEAM_NAME = "Baseline: Greedy Queue"

PHASE_LANES = {
    "NS_STRAIGHT": ("N_straight", "S_straight"),
    "NS_LEFT": ("N_left", "S_left"),
    "EW_STRAIGHT": ("E_straight", "W_straight"),
    "EW_LEFT": ("E_left", "W_left"),
}

SWITCH_MARGIN = 3      # new phase must beat current queue by this many cars
STARVATION_GUARD = 90  # seconds of front-vehicle wait that forces service


class Policy:
    def decide(self, obs) -> str:
        if not obs.can_switch:
            return obs.phase

        def queue_of(phase):
            return sum(obs.queues[lane] for lane in PHASE_LANES[phase])

        # Rescue any lane whose front vehicle is close to starving.
        worst_phase, worst_wait = None, 0
        for phase, lanes in PHASE_LANES.items():
            wait = max(obs.oldest_wait[lane] for lane in lanes)
            if wait > worst_wait:
                worst_phase, worst_wait = phase, wait
        if worst_wait >= STARVATION_GUARD and worst_phase != obs.phase:
            return worst_phase

        best = max(obs.phases, key=queue_of)
        if queue_of(best) > queue_of(obs.phase) + SWITCH_MARGIN:
            return best
        return obs.phase
