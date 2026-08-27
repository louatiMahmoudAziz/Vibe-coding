# Submissions

One folder per team, containing a single `policy.py`:

```
submissions/
  your_team_name/
    policy.py
```

## How to submit

1. Copy the template: `cp -r submissions/_template submissions/your_team_name`
2. Set `TEAM_NAME` inside `policy.py` (this is what the leaderboard shows).
3. Implement `Policy.decide(obs)`.
4. Self-check locally:

   ```bash
   python scripts/validate_submission.py submissions/your_team_name
   python -m traffic_sim.cli evaluate submissions/your_team_name/policy.py
   ```

5. Open a pull request that adds **only your team's folder**. CI evaluates
   every submission automatically and publishes the updated leaderboard.

## Rules

- Python 3 standard library only. No third-party packages, subprocesses,
  file access, or network access.
- Everything must live in your single `policy.py`.
- Compute budget: 10 seconds of wall-clock per run (about 1200 decisions).
- Don't touch the engine, scenarios, scoring, other teams' folders, or CI.
  The organizers re-run the final evaluation on hidden seeds, so overfitting
  to the public seeds is a losing strategy.

The `team_fixed_timer`, `team_greedy_queue` and `team_max_pressure` folders
are organizer-provided baselines. Beat them.
