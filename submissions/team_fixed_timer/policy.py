"""Demo baseline: classic fixed-time signal plan.

A pre-timed controller like a 1970s traffic light: long greens for the
through movements, short greens for the protected lefts, no reaction to
demand whatsoever. Solid on balanced traffic, poor at night and in surges.
"""

TEAM_NAME = "Baseline: Fixed Timer"

# (phase, green seconds) - a fixed cycle, repeated forever.
PLAN = (
    ("NS_STRAIGHT", 24),
    ("NS_LEFT", 10),
    ("EW_STRAIGHT", 24),
    ("EW_LEFT", 10),
)
CYCLE = sum(duration for _, duration in PLAN)


class Policy:
    def decide(self, obs) -> str:
        tick = obs.time % CYCLE
        for phase, duration in PLAN:
            if tick < duration:
                return phase
            tick -= duration
        return PLAN[0][0]
