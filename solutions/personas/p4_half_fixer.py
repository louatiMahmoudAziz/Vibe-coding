"""Right diagnosis, incomplete fix: a wait ceiling with no floor under the
green, so the ceiling itself re-creates the thrashing it was meant to cure.

Persona: The half-fixer
Prompt that produces it:
    Make sure nobody ever waits more than 45 seconds.
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
LANES = {"NS_GREEN": ("north", "south"), "EW_GREEN": ("east", "west")}

MAX_WAIT = 45


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase
        other = OTHER[obs.phase]
        mine = sum(obs.queues[x] for x in LANES[obs.phase])
        theirs = sum(obs.queues[x] for x in LANES[other])
        if max(obs.oldest_wait[x] for x in LANES[other]) >= MAX_WAIT:
            return other
        return other if theirs > mine else obs.phase
