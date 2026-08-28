#!/usr/bin/env python3
"""Pre-workshop check. Run this on the EC2 box before anyone arrives.

    python3 scripts/preflight.py

Exits non-zero if anything would break the workshop. Every check answers a
question you do not want to be asking with twenty people in the room.
"""

from __future__ import annotations

import os
import shutil
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS, FAIL, WARN = "  ok  ", " FAIL ", " warn "
_failed = []
_warned = []


def check(name, fn, fatal=True):
    try:
        detail = fn()
    except Exception as exc:  # noqa: BLE001
        if fatal:
            _failed.append(name)
            print(f"[{FAIL}] {name}\n         {type(exc).__name__}: {exc}")
        else:
            _warned.append(name)
            print(f"[{WARN}] {name}\n         {exc}")
        return False
    print(f"[{PASS}] {name}" + (f"  -  {detail}" if detail else ""))
    return True


# --------------------------------------------------------------------------- #

def c_python():
    if sys.version_info < (3, 9):
        raise RuntimeError(f"Python {sys.version_info.major}.{sys.version_info.minor} "
                           f"is too old; need 3.9+")
    return f"Python {sys.version.split()[0]}"


def c_imports():
    from traffic_sim import engine, metrics, runner, scenarios  # noqa: F401
    from webboard import app, db, evaluator, gateway, pages  # noqa: F401
    return "traffic_sim + webboard import cleanly"


def c_disk():
    free = shutil.disk_usage(".").free / 1e9
    if free < 1.0:
        raise RuntimeError(f"only {free:.1f} GB free")
    return f"{free:.1f} GB free"


def c_port():
    port = int(os.environ.get("VCC_PORT", "8000"))
    sock = socket.socket()
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as exc:
        raise RuntimeError(f"port {port} is already in use ({exc})") from exc
    finally:
        sock.close()
    return f"port {port} is free"


def c_outbound():
    """The classic EC2 trap: private subnet, no NAT, no internet."""
    t0 = time.time()
    try:
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models",
            method="GET",
        )
        urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError:
        pass  # 400/403 without a key is fine - we reached Google
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"cannot reach generativelanguage.googleapis.com ({exc.reason}). "
            f"Check the subnet has an internet gateway or NAT."
        ) from exc
    return f"reached Google in {(time.time()-t0)*1000:.0f} ms"


def c_key():
    from webboard import gateway
    source = gateway.key_source()
    if source == "unset":
        raise RuntimeError("no key configured (GEMINI_API_KEY / VCC_SECRET_ID / VCC_SSM_PARAM)")
    key = gateway._api_key()
    # Google issues both the legacy "AIza..." keys and the newer "AQ." format.
    # Don't gate on a prefix - a real generation is the only honest check, and
    # c_generation() below does exactly that.
    if len(key) < 20:
        raise RuntimeError("key resolved but is implausibly short")
    return f"{source}  ->  {key[:3]}...{key[-4:]} ({len(key)} chars)"


def c_generation():
    """A real end-to-end generation, priced in cents, worth every one."""
    from webboard import db, gateway
    tmp = Path(tempfile.mkdtemp()) / "preflight.sqlite3"
    db.init(tmp)
    gateway.ensure_schema(tmp)
    pid = db.create_participant(tmp, "preflight", "preflight-pw")["id"]
    t0 = time.time()
    gen = gateway.generate(tmp, pid, "Implement an adaptive traffic controller.")
    elapsed = time.time() - t0
    if "class Policy" not in gen.code:
        raise RuntimeError("generation returned no Policy class")
    return (f"{gateway.MODEL} in {elapsed:.1f}s, {gen.charged} tokens, "
            f"{gen.remaining} left of {gateway.DEFAULT_BUDGET_TOKENS}")


def c_evaluator():
    from traffic_sim.runner import evaluate_submission
    t0 = time.time()
    result = evaluate_submission(Path("submissions/team_max_pressure/policy.py"))
    if result.load_error:
        raise RuntimeError(result.load_error)
    return f"baseline scored {result.total:.1f} in {time.time()-t0:.1f}s"


def c_config():
    from webboard import gateway
    if gateway.TEMPERATURE != 0.0:
        raise RuntimeError(f"temperature is {gateway.TEMPERATURE}, expected 0")
    return (f"model={gateway.MODEL} temp={gateway.TEMPERATURE} "
            f"budget={gateway.DEFAULT_BUDGET_TOKENS} "
            f"concurrency={gateway.MAX_CONCURRENT} rpm={gateway.TARGET_RPM}")


def c_rpm_sanity():
    from webboard import gateway
    if gateway.TARGET_RPM > 2000:
        raise RuntimeError(f"VCC_TARGET_RPM={gateway.TARGET_RPM} looks higher than any "
                           f"real tier limit; 429s will do your shaping instead")
    if gateway.TARGET_RPM < 120:
        raise RuntimeError(f"VCC_TARGET_RPM={gateway.TARGET_RPM} will serialise "
                           f"participants behind one another (measured: 78s worst wait at 60)")
    return f"{gateway.TARGET_RPM} rpm is a sane shaping target"


print("=" * 70)
print("VIBE CODING CHALLENGE - PREFLIGHT")
print("=" * 70)
check("python version", c_python)
check("project imports", c_imports)
check("disk space", c_disk)
check("http port free", c_port, fatal=False)
check("outbound internet to Google", c_outbound)
check("api key resolves", c_key)
check("gateway config", c_config)
check("rate-limit shaping sane", c_rpm_sanity, fatal=False)
check("evaluator runs", c_evaluator)
check("END-TO-END generation", c_generation)

print("=" * 70)
if _failed:
    print(f"NOT READY - {len(_failed)} blocking failure(s): {', '.join(_failed)}")
    raise SystemExit(1)
if _warned:
    print(f"READY, with warnings: {', '.join(_warned)}")
    raise SystemExit(0)
print("READY. Start the server with:  make serve")
raise SystemExit(0)
