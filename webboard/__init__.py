"""Live leaderboard web app for the Traffic Flow Challenge.

Participants sign up with their name via a link, receive a personal upload
page, and every code upload is evaluated automatically; the leaderboard
updates live. Standard library only: http.server + sqlite3 + a worker
thread that runs each evaluation in an isolated subprocess.

Run it:  python -m webboard --port 8000 --data server_data
"""

__version__ = "1.0.0"
