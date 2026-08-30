"""A loose ceiling found by iteration rather than reasoning. Passes every act
because 120 s is under the 140 s limit: the concept earns the pass, the
missing calibration costs the win.

Persona: The vibe-coding native
Prompt that produces it:
    Do not let anyone sit longer than 2 minutes.
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
LANES = {"NS_GREEN": ("north", "south"), "EW_GREEN": ("east", "west")}

MAX_WAIT = 120
MARGIN = 3


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase
        other = OTHER[obs.phase]
        mine = sum(obs.queues[x] for x in LANES[obs.phase])
        theirs = sum(obs.queues[x] for x in LANES[other])
        if max(obs.oldest_wait[x] for x in LANES[other]) >= MAX_WAIT:
            return other
        return other if theirs > mine + MARGIN else obs.phase
