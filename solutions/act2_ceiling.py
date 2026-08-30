"""ACT 2 SOLVER - a ceiling that outranks the margin, and greens long enough to be worth taking.

The Act 1 controller was not broken. Its idea of "which phase needs the green"
counted cars and never counted time, so a small queue could sit indefinitely.
The obvious fix - a hard ceiling on waiting - is necessary but not sufficient,
and the reason is the part worth understanding.

Every switch costs six seconds in which nothing moves. A controller that reacts
to every ceiling breach switches constantly and loses a third of the clock to
yellow lights; it stops stranding anybody and starts failing throughput and
average wait instead. Measured: a naive ceiling at 55s produced 57 switches in
a 600-second run - 342 seconds of dead time.

So this policy has two ideas, and needs both:

  1. A ceiling that is checked FIRST, before any pressure comparison. If a
     phase has somebody over MAX_WAIT it gets the green next, full stop. Put
     this check after the pressure logic and the switching margin swallows it.

  2. A green worth taking. Once a phase is green it keeps it until it has
     actually drained, or MIN_SERVE seconds have passed - so the six seconds
     spent getting there buy something.

The two pull against each other. That tension is the problem.
"""

TEAM_NAME = "Reference: Act 2"

PHASE_LANES = {
    "NS_STRAIGHT": ("N_straight", "S_straight"),
    "NS_LEFT": ("N_left", "S_left"),
    "EW_STRAIGHT": ("E_straight", "W_straight"),
    "EW_LEFT": ("E_left", "W_left"),
}

MAX_WAIT = 95        # hard ceiling; the requirement is 140s, leave room to be served
MIN_SERVE = 18       # keep a green at least this long, so the switch cost buys something
AGE_WEIGHT = 0.5     # a second of waiting is worth this much of a queued car
SWITCH_MARGIN = 4    # how much better a rival must look before paying six seconds


def _queue(obs, phase):
    return sum(obs.queues[lane] for lane in PHASE_LANES[phase])


def _oldest(obs, phase):
    return max(obs.oldest_wait[lane] for lane in PHASE_LANES[phase])


class Policy:
    def decide(self, obs):
        if not obs.can_switch:
            return obs.phase

        # 1. THE CEILING. Nothing below may override this.
        starving, longest = None, MAX_WAIT
        for phase in PHASE_LANES:
            if phase == obs.phase:
                continue
            waited = _oldest(obs, phase)
            if waited > longest:
                starving, longest = phase, waited
        if starving is not None:
            return starving

        here = _queue(obs, obs.phase)

        # 2. Nobody left to serve: move on, whoever is waiting.
        if here == 0:
            best, best_score = obs.phase, 0.0
            for phase in PHASE_LANES:
                score = _queue(obs, phase) + AGE_WEIGHT * _oldest(obs, phase)
                if score > best_score:
                    best, best_score = phase, score
            return best

        # 3. Otherwise finish what we started. A green shorter than this wastes
        #    more in switching than it recovers in service.
        if obs.phase_elapsed < MIN_SERVE:
            return obs.phase

        # 4. Pressure, with age folded in, and a margin to stop dithering.
        def pressure(phase):
            return _queue(obs, phase) + AGE_WEIGHT * _oldest(obs, phase)

        mine = pressure(obs.phase)
        best, best_score = obs.phase, mine
        for phase in PHASE_LANES:
            score = pressure(phase)
            if score > best_score:
                best, best_score = phase, score

        if best_score > mine + SWITCH_MARGIN:
            return best
        return obs.phase
