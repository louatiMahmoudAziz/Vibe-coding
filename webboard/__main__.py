"""Run the live leaderboard server.

    python -m webboard --port 8000 --data server_data
    python -m webboard --seeds 9241,7717,3583   # e.g. a hidden-seed finals board
"""

from __future__ import annotations

import argparse

from .app import serve


def main() -> int:
    parser = argparse.ArgumentParser(prog="webboard", description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--data",
        default="server_data",
        help="directory for the database and uploaded code (default: server_data)",
    )
    parser.add_argument(
        "--seeds", help="comma-separated evaluation seeds (default: public seeds)"
    )
    args = parser.parse_args()

    seeds = (
        tuple(int(s) for s in args.seeds.split(",") if s.strip())
        if args.seeds
        else None
    )
    server = serve(args.host, args.port, args.data, seeds)
    host, port = server.server_address[:2]
    shown_host = "localhost" if host in ("0.0.0.0", "::") else host
    print("Traffic Flow Challenge leaderboard server")
    print(f"  leaderboard : http://{shown_host}:{port}/")
    print(f"  signup link : http://{shown_host}:{port}/signup")
    print(f"  data dir    : {args.data}")
    print(f"  seeds       : {', '.join(map(str, server.seeds))}")
    print("Share the signup link with participants. Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        server.evaluator.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
