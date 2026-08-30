"""Reference solver, Acts 2 and 3: bound the worst case, then optimise.

Three rules, and the ORDER MATTERS.

  1. Ceiling first. If anyone on the red road has waited MAX_WAIT seconds,
     switch -- regardless of queue lengths. This is what the side street
     needs, and it is why a queue comparison alone can never be enough.
  2. But not before MIN_SERVE seconds of green. Without this the ceiling
     itself causes thrashing, and thrashing fails throughput. The two
     numbers are a pair; neither works alone.
  3. Otherwise compare queues with a margin, so the light does not flip
     over a one-car difference that is not worth six seconds of dead time.

Measured:  ACT 1 pass  |  ACT 2 pass  |  DEPLOYMENT pass (all 7 traces)
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
LANES = {"NS_GREEN": ("north", "south"), "EW_GREEN": ("east", "west")}

MAX_WAIT = 70      # nobody on red waits longer than this
MIN_SERVE = 16     # ...but give the green road at least this long first
MARGIN = 3         # queue difference worth paying 6 s of dead time for


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase
        other = OTHER[obs.phase]
        mine = sum(obs.queues[lane] for lane in LANES[obs.phase])
        theirs = sum(obs.queues[lane] for lane in LANES[other])
        their_wait = max(obs.oldest_wait[lane] for lane in LANES[other])

        # 1 + 2: the ceiling, guarded by a minimum serve time.
        if their_wait >= MAX_WAIT and obs.phase_elapsed >= MIN_SERVE:
            return other
        # Nobody here, somebody there: no reason to hold.
        if mine == 0 and theirs > 0:
            return other
        # 3: ordinary pressure comparison, damped.
        return other if theirs > mine + MARGIN else obs.phase
