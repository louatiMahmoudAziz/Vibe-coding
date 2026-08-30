"""Demo baseline: always serve whoever has more cars waiting, right now.

The first thing almost everyone writes, and it passes the pilot. Under a
real rush it flips the lights ~54 times in ten minutes; at six seconds of
dead time per change that is more than five minutes with nobody moving.
Measured on the rush trace: 77% of traffic served, 56 s average wait.
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
