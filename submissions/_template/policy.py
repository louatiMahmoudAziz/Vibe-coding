"""Starting point for a controller.

The intersection has four approaches -- north, south, east, west -- and two
phases. Exactly one is green at a time:

    "NS_GREEN"   north and south move, east and west wait
    "EW_GREEN"   east and west move, north and south wait

`decide` is called once per simulated second and returns the phase it wants
green. Returning the phase that is already green holds the light.

The engine enforces safety, not you: a green is held at least obs.min_green
seconds, and every change costs obs.yellow + obs.all_red seconds of dead time
plus two seconds of startup before anyone moves again. A switch requested when
a switch is impossible is simply ignored.

What you can see each tick:

    obs.time                 int, current second
    obs.horizon              int, total run length in seconds
    obs.phase                str, the phase that is green now
    obs.phase_elapsed        int, seconds it has been green
    obs.can_switch           bool, True if a switch would take effect now
    obs.queues               dict, e.g. obs.queues["north"] -> cars waiting
    obs.oldest_wait          dict, e.g. obs.oldest_wait["north"] -> seconds
                             the front car there has been waiting
    obs.min_green, obs.yellow, obs.all_red, obs.phases
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
