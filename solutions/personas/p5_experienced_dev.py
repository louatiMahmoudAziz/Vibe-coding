"""Margin plus a blunt cap on green time. Passes every act. Second place.

Persona: The experienced dev
Prompt that produces it:
    Do not switch for a trivial difference, and cap how long one road holds green.
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
LANES = {"NS_GREEN": ("north", "south"), "EW_GREEN": ("east", "west")}

MARGIN = 3
MAX_GREEN = 45


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase
        other = OTHER[obs.phase]
        mine = sum(obs.queues[x] for x in LANES[obs.phase])
        theirs = sum(obs.queues[x] for x in LANES[other])
        if obs.phase_elapsed >= MAX_GREEN:
            return other
        return other if theirs > mine + MARGIN else obs.phase
