"""Reference solver, Act 1: the lazy answer.

What a participant gets from "serve whoever has the longest queue". It
clears Act 1 comfortably and is meant to. It then fails Act 2's rush trace
on all three gates at once, because it switches ~54 times in ten minutes
and each change costs six seconds in which nobody moves.

Measured:  ACT 1 pass  |  ACT 2 fail (throughput 0.77, avg wait 56 s)
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
LANES = {"NS_GREEN": ("north", "south"), "EW_GREEN": ("east", "west")}


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase
        other = OTHER[obs.phase]
        mine = sum(obs.queues[lane] for lane in LANES[obs.phase])
        theirs = sum(obs.queues[lane] for lane in LANES[other])
        return other if theirs > mine else obs.phase
