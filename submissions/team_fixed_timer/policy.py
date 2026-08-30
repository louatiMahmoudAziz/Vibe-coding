"""Demo baseline: a dumb clock. Thirty seconds each way, forever.

It ignores traffic completely, which makes it a useful yardstick: any
controller that cannot beat a fixed timer is not doing anything useful.
It survives the pilot and both complaints, then falls apart on deployment
traces whose demand is nothing like the pilot's.
"""

OTHER = {"NS_GREEN": "EW_GREEN", "EW_GREEN": "NS_GREEN"}
SPAN = 30


class Policy:
    def decide(self, obs):
        return obs.phase if obs.phase_elapsed < SPAN else OTHER[obs.phase]
