"""Longest queue wins, no damping. Flips ~54 times in ten minutes.

Persona: The first-year CS student
Prompt that produces it:
    Compare how many cars are waiting and give green to whichever has more.
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
LANES = {"NS_GREEN": ("north", "south"), "EW_GREEN": ("east", "west")}


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase
        other = OTHER[obs.phase]
        mine = sum(obs.queues[x] for x in LANES[obs.phase])
        theirs = sum(obs.queues[x] for x in LANES[other])
        return other if theirs > mine else obs.phase
