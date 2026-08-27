# Live Leaderboard Server Guide

`webboard` is a self-hosted web app for running the challenge with signup
links and automatic evaluation on upload. Standard library only — if the
machine has Python 3.10+, it runs.

## What participants experience

1. They open the **signup link** you share (`http://<host>:8000/signup`),
   create an account (name + password), and land on their personal upload
   page. The browser **stays signed in** (30-day session cookie) until they
   log out via the menu under their name in the top-right corner; from
   another device they log in at `http://<host>:8000/login`. Opening a
   bookmarked personal-page URL also signs that browser in.
2. They upload their AI-generated `policy.py` (file picker or paste box)
   as often as they like — a 15 s cooldown stops accidental spam.
3. Each upload is queued and evaluated automatically (5 scenarios × 3
   seeds, same harness as the CLI). Their page shows live status:
   `evaluating…` → `scored` (with per-scenario breakdown) or `error` (with
   the exact exception).
4. The main page (`http://<host>:8000/`) is the live leaderboard: ranked
   by **best** submission, refreshing every 4 seconds. Project it.

## Running it

```bash
python -m webboard --port 8000 --data server_data
```

- `--data` holds everything: `board.sqlite3` plus every uploaded file
  under `uploads/p<id>/s<n>.py`. Back up that one folder and you have the
  whole event.
- `--seeds 7,8,9` changes the evaluation seeds (defaults to the public
  seeds `101,202,303`).
- Restart-safe: evaluations interrupted by a restart are re-queued on boot.

## Running it on AWS (EC2)

```bash
# Ubuntu 24.04 AMI, t3.micro is fine; security group: allow TCP 8000
sudo apt-get update && sudo apt-get install -y git
git clone <your-repo-url> && cd <repo>
python3 -m unittest discover -s tests          # optional self-check

# keep it alive after you disconnect
sudo tee /etc/systemd/system/trafficboard.service > /dev/null <<'EOF'
[Unit]
Description=Traffic Flow Challenge leaderboard
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/<repo>
ExecStart=/usr/bin/python3 -m webboard --port 8000 --data /home/ubuntu/server_data
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now trafficboard
```

Share `http://<ec2-public-ip>:8000/signup` with participants and put
`http://<ec2-public-ip>:8000/` on the projector.

Security notes for the venue:

- Uploaded code runs on this machine (in an isolated subprocess with a hard
  timeout, so it can't hang or crash the server — but it is still arbitrary
  code). Use a **disposable instance** with a no-permission IAM role and no
  secrets, restrict the security group to the venue's IP range if you can,
  and terminate it after the event.
- The signup link is open by design (anyone with it can register a name).
  For a public network, keep the URL unlisted or restrict by source IP.
- Passwords are salted PBKDF2-SHA256 hashes in the SQLite database, and
  accounts created before the login feature keep working via their
  bookmark link (they just can't use the login form). There is no
  password-reset flow — for a lost password, an organizer can look up the
  participant's page token: `sqlite3 server_data/board.sqlite3 "SELECT
  name, token FROM participants"` and hand back `http://<host>:8000/p/<token>`.

## How evaluation works

- Uploads land in a queue; a single worker evaluates them one at a time by
  shelling out to `python -m traffic_sim.cli evaluate <file> --json`
  (240 s hard timeout). One evaluation takes about a second, so even a
  burst of 30 uploads drains in under a minute; the leaderboard shows the
  queue depth while it works.
- Crashes, invalid phases, forbidden returns, syntax errors and timeouts
  become an `error` status with the message shown to the participant —
  the server never goes down with a submission.
- Ranking: **best** scored submission per participant; ties broken by who
  reached the score first, so sniping an identical score doesn't steal a
  podium.

## Finals on hidden seeds

Export every participant's best upload into a standard `submissions/`
layout, then score it with the offline tool and your secret seeds:

```bash
python scripts/export_server_submissions.py --data server_data --out finals_submissions
python scripts/build_leaderboard.py --submissions finals_submissions \
    --seeds 9241,7717,3583 --out results_final
# reveal results_final/leaderboard.html on the projector
```

Alternatively, run a second (hidden) server with `--seeds` and re-upload —
but the export path is simpler and keeps the finals reproducible.

## Endpoints (for scripting)

| Route | What |
|-------|------|
| `GET /` | live leaderboard page |
| `GET /signup`, `POST /signup` | account creation (name + password) |
| `GET /login`, `POST /login` | log in (starts a 30-day session cookie) |
| `GET /me` | redirect to your upload page (session cookie required) |
| `GET /logout` | end the session and return to the leaderboard |
| `GET /api/session` | who am I (drives the top-right user menu) |
| `GET /p/<token>` | personal upload page (secret) |
| `POST /p/<token>/upload` | submit code (multipart file or `code` field) |
| `GET /api/leaderboard` | standings JSON (what the page polls) |
| `GET /api/participant/<token>` | one participant's history JSON |
| `GET /health` | liveness + evaluation backlog |
