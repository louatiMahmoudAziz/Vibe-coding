"""Max-pressure with a margin. Best average wait in the field; starves the
side street at 188 s. The vocabulary was right, the number was not.

Persona: The algorithms student
Prompt that produces it:
    Implement max-pressure control with an aging term to prevent starvation.
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
LANES = {"NS_GREEN": ("north", "south"), "EW_GREEN": ("east", "west")}

MARGIN = 3


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase
        other = OTHER[obs.phase]
        mine = sum(obs.queues[x] for x in LANES[obs.phase])
        theirs = sum(obs.queues[x] for x in LANES[other])
        return other if theirs > mine + MARGIN else obs.phase
