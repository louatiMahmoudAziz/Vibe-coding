"""ACT 1 SOLVER - and the trap, in one file.

This is what a lazy prompt produces: serve whichever phase has the longest
queue, with a margin so it does not flip on every tick. It passes Act 1
comfortably, which is exactly the point - Act 1 is supposed to feel easy.

It fails Act 2, and the reason is worth understanding before you run the
workshop. The margin below (`SWITCH_MARGIN`) is what stops the controller
thrashing between near-equal phases. It is also what guarantees the left-turn
lanes starve: a lane with two cars can never beat a lane with fifteen, no
matter how long those two cars have been sitting there. The fix for one
problem causes the other, and no value of the margin resolves both.

Nothing here is wrong. It does precisely what it was asked to do.
"""

TEAM_NAME = "Reference: Act 1 (fails Act 2 on purpose)"

PHASE_LANES = {
    "NS_STRAIGHT": ("N_straight", "S_straight"),
    "NS_LEFT": ("N_left", "S_left"),
    "EW_STRAIGHT": ("E_straight", "W_straight"),
    "EW_LEFT": ("E_left", "W_left"),
}

SWITCH_MARGIN = 3      # how much better another phase must look before we move


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase

        current = sum(obs.queues[lane] for lane in PHASE_LANES[obs.phase])

        # Never hold a green that nobody is using.
        if current == 0:
            for phase, lanes in PHASE_LANES.items():
                if sum(obs.queues[lane] for lane in lanes) > 0:
                    return phase
            return obs.phase

        best, best_queue = obs.phase, current
        for phase, lanes in PHASE_LANES.items():
            queued = sum(obs.queues[lane] for lane in lanes)
            if queued > best_queue:
                best, best_queue = phase, queued

        if best_queue > current + SWITCH_MARGIN:
            return best
        return obs.phase
