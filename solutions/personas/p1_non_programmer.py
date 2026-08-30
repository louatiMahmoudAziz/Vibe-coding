"""Alternates on a short timer. No idea traffic exists.

Persona: The non-programmer
Prompt that produces it:
    Make the traffic flow well and be fair to everyone.
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
LANES = {"NS_GREEN": ("north", "south"), "EW_GREEN": ("east", "west")}


class Policy:
    def decide(self, obs):
        return obs.phase if obs.phase_elapsed < 8 else OTHER[obs.phase]
