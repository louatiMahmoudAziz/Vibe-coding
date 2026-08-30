# Reference solutions — organiser only

Do not put these in front of participants. They exist to prove the challenge is
solvable, to calibrate thresholds, and to give you something concrete for the
debrief.

| file | passes | what it is |
| --- | --- | --- |
| `act1_naive.py` | Act 1 | What a lazy prompt produces. Longest queue wins, with a margin to stop flip-flopping. Fails Act 2 and deployment. |
| `act2_ceiling.py` | Act 1, Act 2, deployment | The real answer. A hard waiting ceiling checked *before* the pressure comparison, plus a minimum useful green so switching cost buys something. |

## The one idea that separates them

`act1_naive` ranks phases by how many cars are waiting, never by how long. A
lane with two cars can never beat a lane with fifteen, so the left-turn lanes
starve. The margin that stops the controller thrashing is exactly what
guarantees it.

`act2_ceiling` fixes that with two changes, and needs both:

1. **A ceiling checked first.** Anyone over `MAX_WAIT` gets the green next,
   before any pressure comparison runs. Put this check *after* the pressure
   logic and the switching margin swallows it — the most common way to write
   this and have it silently not work.

2. **A green worth taking.** `MIN_SERVE` keeps a phase green long enough that
   the six seconds spent getting there buys some service.

The second one is not optional and it is not obvious. A ceiling on its own
switches constantly: measured, a 55-second ceiling with no minimum green
produced 57 switches in a 600-second run — 342 seconds of dead time — and
failed *throughput* while fixing starvation. Getting from "add a fairness rule"
to "add a fairness rule without destroying capacity" is the actual engineering,
and it is what separates participants.

## Using them

```bash
python3 -m traffic_sim.cli evaluate solutions/act2_ceiling.py --act deployment
```

Before the workshop, run both through every act. If `act1_naive` passes Act 2,
the trap is too weak. If `act2_ceiling` fails anything, the thresholds are too
tight and Act 2 is unwinnable.

## For the debrief

Put the two `decide()` methods side by side. The difference is about fifteen
lines, both were written to satisfy a client, and one of them strands people
for six minutes. That is the whole workshop in one diff.
