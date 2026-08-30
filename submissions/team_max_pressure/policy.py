"""Demo baseline: greedy, but only switch when it is clearly worth 6 seconds.

The obvious fix for a flickering light, and it works: throughput recovers
and the average wait is the best in the field. It also starves the side
street, because a queue of one never beats a queue of twelve by four.
Measured on the side-street trace: 5.7 s average wait, 188 s worst wait.

This controller is the whole point of the challenge. Its dashboard is
excellent and it is not acceptable.
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
LANES = {"NS_GREEN": ("north", "south"), "EW_GREEN": ("east", "west")}
MARGIN = 3


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase
        other = OTHER[obs.phase]
        mine = sum(obs.queues[lane] for lane in LANES[obs.phase])
        theirs = sum(obs.queues[lane] for lane in LANES[other])
        return other if theirs > mine + MARGIN else obs.phase
