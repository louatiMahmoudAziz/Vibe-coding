"""Demo baseline: max-pressure-style controller with aging and switch cost.

Each phase is scored by the demand it would serve, where a vehicle's value
grows with its waiting time (aging prevents starvation organically). The
controller stays on the current phase unless a competitor's pressure beats
it by more than the modeled cost of switching, and it extends greens only
while they are still discharging vehicles.
"""

TEAM_NAME = "Baseline: Max Pressure"

PHASE_LANES = {
    "NS_STRAIGHT": ("N_straight", "S_straight"),
    "NS_LEFT": ("N_left", "S_left"),
    "EW_STRAIGHT": ("E_straight", "W_straight"),
    "EW_LEFT": ("E_left", "W_left"),
}

AGING = 0.01          # extra pressure per second the front vehicle has waited
SWITCH_COST = 8.0     # pressure advantage needed to justify ~6 dead seconds
MAX_GREEN = 60        # never hold one green longer than this with rivals waiting
HARD_STARVE = 150     # front-vehicle wait that forces immediate service


class Policy:
    def pressure(self, obs, phase) -> float:
        total = 0.0
        for lane in PHASE_LANES[phase]:
            queue = obs.queues[lane]
            total += queue * (1.0 + AGING * obs.oldest_wait[lane])
        return total

    def decide(self, obs) -> str:
        if not obs.can_switch:
            return obs.phase

        # Hard anti-starvation override.
        for phase, lanes in PHASE_LANES.items():
            if phase == obs.phase:
                continue
            if max(obs.oldest_wait[lane] for lane in lanes) >= HARD_STARVE:
                return phase

        current = self.pressure(obs, obs.phase)
        rivals = {p: self.pressure(obs, p) for p in obs.phases if p != obs.phase}
        best = max(rivals, key=rivals.get)

        current_empty = all(obs.queues[lane] == 0 for lane in PHASE_LANES[obs.phase])
        if current_empty and rivals[best] > 0:
            return best
        if obs.phase_elapsed >= MAX_GREEN and rivals[best] > 0:
            return best
        if rivals[best] > current + SWITCH_COST:
            return best
        return obs.phase
