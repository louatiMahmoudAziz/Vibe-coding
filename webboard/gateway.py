"""AI gateway: the only route from a participant to the model.

Design rules this module enforces
---------------------------------
* The API key lives here, server-side. It is never sent to a browser.
* Model and temperature are pinned in config, not chosen per request, so
  the challenge is reproducible run-to-run and year-to-year.
* Temperature is 0. Two participants who send the same prompt get the same
  controller; differences in outcome come from differences in direction,
  which is the thing the challenge claims to measure.
* Every participant has a token budget. Spend is metered from the
  provider's own usage numbers, never from a local estimate.
* A generation that does not produce loadable code is refunded. Paying
  budget to fix a syntax error teaches nothing.
* The interface spec is supplied as a system instruction, so nobody burns
  budget re-explaining the `obs` object.

Stdlib only, in keeping with the rest of the project.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from . import db

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
MODEL = os.environ.get("VCC_MODEL", "gemini-2.5-flash")
API_KEY_ENV = "GEMINI_API_KEY"

TEMPERATURE = 0.0          # see module docstring: this is deliberate
MAX_OUTPUT_TOKENS = 2000   # one runaway generation cannot eat a whole budget
REQUEST_TIMEOUT_S = 45
MAX_PROMPT_CHARS = 4000    # a participant prompt longer than this is truncated

DEFAULT_BUDGET_TOKENS = int(os.environ.get("VCC_BUDGET_TOKENS", "35000"))

# Traffic shaping. Twenty participants prompt within seconds of each other
# when a round is announced; these turn that spike into a smooth stream.
MAX_CONCURRENT = int(os.environ.get("VCC_MAX_CONCURRENT", "8"))
TARGET_RPM = int(os.environ.get("VCC_TARGET_RPM", "600"))
# NOTE: set VCC_TARGET_RPM to ~80% of the real limit shown in AI Studio.
# Too low serialises everyone behind one spacer (measured: 78s worst
# wait for 20 simultaneous submits at 60 RPM); too high just means the
# 429 backoff below does the shaping instead.
RETRY_ON_429 = 4          # upstream throttle retries, never charged
BACKOFF_BASE_S = 1.5
MAX_QUEUE_WAIT_S = 120    # give up rather than leave someone spinning forever

# Retries that cost the participant nothing.
FREE_RETRIES = 2

PHASES = ("NS_STRAIGHT", "NS_LEFT", "EW_STRAIGHT", "EW_LEFT")

SYSTEM_INSTRUCTION = """\
You write traffic-signal control policies in Python for a discrete-time \
simulator. You return code and nothing else.

Contract — your output MUST be a single ```python block containing a class \
named `Policy` with a method `decide(self, obs)`. It is called once per \
simulated second and must return one of these strings:

    "NS_STRAIGHT"   opens lanes N_straight and S_straight
    "NS_LEFT"       opens lanes N_left     and S_left
    "EW_STRAIGHT"   opens lanes E_straight and W_straight
    "EW_LEFT"       opens lanes E_left     and W_left

Returning the current phase (or None) holds the light. The engine enforces \
safety: a green is held at least `obs.min_green` seconds, and every change \
burns `obs.yellow + obs.all_red` seconds of dead time in which no vehicle \
moves. Switch requests made when a switch is impossible are ignored, so it \
is safe to return your desired phase every tick.

The `obs` object each tick:

    obs.time                int, current second
    obs.horizon             int, total scenario length in seconds
    obs.phase               str, active (or most recent) green phase
    obs.phase_elapsed       int, seconds the current green has been held
    obs.in_transition       bool, True during yellow / all-red
    obs.transition_remaining int, seconds left in the transition
    obs.can_switch          bool, True if a switch would take effect now
    obs.queues              dict lane -> queued vehicle count
    obs.oldest_wait         dict lane -> seconds the FRONT vehicle has waited
    obs.arrivals_total      int, vehicles arrived so far
    obs.served_total        int, vehicles that have crossed so far
    obs.min_green, obs.yellow, obs.all_red, obs.phases

Lane names are exactly: N_straight, N_left, S_straight, S_left, \
E_straight, E_left, W_straight, W_left.

Rules for your output:
* No imports. No file, network, or system access. Pure computation only.
* `decide` must be fast; it runs once per simulated second for thousands of \
seconds and the whole run has a 10-second wall-clock budget.
* You may keep state on `self`. If you define `reset(self)` it is called \
once before each run — use it to clear state between runs.
* Output ONLY the ```python block. No explanation before or after.
"""

CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


class GatewayError(RuntimeError):
    """Upstream or configuration failure. Never charged to the participant."""


class BudgetExhausted(RuntimeError):
    """The participant has no tokens left."""


@dataclass
class Generation:
    code: str
    raw_text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    charged: int
    attempts: int
    remaining: int
    refunded: bool = False
    note: Optional[str] = None



# --------------------------------------------------------------------------- #
# Storage
#
# The gateway owns its own tables and creates them on demand, so it bolts on
# without touching db.py. `ensure_schema` is idempotent; call it at startup.
# --------------------------------------------------------------------------- #

GATEWAY_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_budget (
    participant_id INTEGER PRIMARY KEY REFERENCES participants (id),
    granted        INTEGER NOT NULL,
    spent          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ai_calls (
    id             INTEGER PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participants (id),
    created_at     REAL    NOT NULL,
    model          TEXT    NOT NULL,
    temperature    REAL    NOT NULL,
    prompt         TEXT    NOT NULL,
    response_text  TEXT    NOT NULL,
    code           TEXT    NOT NULL,
    input_tokens   INTEGER NOT NULL,
    output_tokens  INTEGER NOT NULL,
    charged        INTEGER NOT NULL,
    attempt        INTEGER NOT NULL,
    latency_s      REAL    NOT NULL,
    error          TEXT
);
CREATE INDEX IF NOT EXISTS idx_ai_calls_participant
    ON ai_calls (participant_id, created_at);
"""


def ensure_schema(db_path: Path) -> None:
    with db.connect(db_path) as conn:
        conn.executescript(GATEWAY_SCHEMA)


def _ensure_budget_row(conn, participant_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO ai_budget (participant_id, granted, spent) "
        "VALUES (?, ?, 0)",
        (participant_id, DEFAULT_BUDGET_TOKENS),
    )


def budget_state(db_path: Path, participant_id: int) -> Dict[str, int]:
    with db.connect(db_path) as conn:
        _ensure_budget_row(conn, participant_id)
        row = conn.execute(
            "SELECT granted, spent FROM ai_budget WHERE participant_id = ?",
            (participant_id,),
        ).fetchone()
    granted, spent = int(row["granted"]), int(row["spent"])
    remaining = max(0, granted - spent)
    return {
        "granted": granted,
        "spent": spent,
        "remaining": remaining,
        "percent": round(100.0 * remaining / granted, 1) if granted else 0.0,
    }


def budget_remaining(db_path: Path, participant_id: int) -> int:
    return budget_state(db_path, participant_id)["remaining"]


def spend_budget(db_path: Path, participant_id: int, tokens: int) -> int:
    """Charge tokens atomically and return what is left."""
    with db.connect(db_path) as conn:
        _ensure_budget_row(conn, participant_id)
        conn.execute(
            "UPDATE ai_budget SET spent = spent + ? WHERE participant_id = ?",
            (int(tokens), participant_id),
        )
        row = conn.execute(
            "SELECT granted, spent FROM ai_budget WHERE participant_id = ?",
            (participant_id,),
        ).fetchone()
    return max(0, int(row["granted"]) - int(row["spent"]))


def grant_budget(db_path: Path, participant_id: int, tokens: int) -> Dict[str, int]:
    """Organizer escape hatch: top a participant up mid-session."""
    with db.connect(db_path) as conn:
        _ensure_budget_row(conn, participant_id)
        conn.execute(
            "UPDATE ai_budget SET granted = granted + ? WHERE participant_id = ?",
            (int(tokens), participant_id),
        )
    return budget_state(db_path, participant_id)


def record_call(db_path: Path, **fields) -> None:
    with db.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO ai_calls (participant_id, created_at, model, temperature, "
            "prompt, response_text, code, input_tokens, output_tokens, charged, "
            "attempt, latency_s, error) "
            "VALUES (:participant_id, :created_at, :model, :temperature, :prompt, "
            ":response_text, :code, :input_tokens, :output_tokens, :charged, "
            ":attempt, :latency_s, :error)",
            {"created_at": time.time(), **fields},
        )


def call_log(db_path: Path, participant_id: int) -> list:
    """Everything this participant asked for, in order. Debrief material."""
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT created_at, prompt, code, input_tokens, output_tokens, "
            "charged, attempt, latency_s, error FROM ai_calls "
            "WHERE participant_id = ? ORDER BY created_at",
            (participant_id,),
        ).fetchall()
    return [dict(row) for row in rows]



# --------------------------------------------------------------------------- #
# Traffic shaping
#
# Three independent guards, because the failure mode is a live workshop:
#   * a semaphore caps how many requests are in flight at once
#   * a spacer enforces a minimum gap between upstream calls (the RPM budget)
#   * a per-participant lock stops one person queueing five requests in parallel
# Waiting is reported through a callback so the UI can say "3 ahead of you"
# instead of showing a dead spinner.
# --------------------------------------------------------------------------- #


class _RateLimiter:
    def __init__(self, max_concurrent: int, target_rpm: int):
        self._slots = threading.Semaphore(max_concurrent)
        self._spacing = 60.0 / max(1, target_rpm)
        self._gate = threading.Lock()
        self._next_slot_at = 0.0
        self._waiting = 0
        self._counter_lock = threading.Lock()

    @property
    def waiting(self) -> int:
        with self._counter_lock:
            return self._waiting

    @contextmanager
    def slot(self, timeout: float = MAX_QUEUE_WAIT_S):
        with self._counter_lock:
            self._waiting += 1
        try:
            if not self._slots.acquire(timeout=timeout):
                raise GatewayError(
                    "the AI gateway is busy and your request timed out. "
                    "Nothing was charged - try again in a moment."
                )
        finally:
            with self._counter_lock:
                self._waiting -= 1
        try:
            # Space calls out so the whole server stays under TARGET_RPM.
            with self._gate:
                now = time.monotonic()
                wait = self._next_slot_at - now
                if wait > 0:
                    time.sleep(wait)
                    now = time.monotonic()
                self._next_slot_at = now + self._spacing
            yield
        finally:
            self._slots.release()


_limiter = _RateLimiter(MAX_CONCURRENT, TARGET_RPM)
_participant_locks: Dict[int, threading.Lock] = {}
_participant_locks_guard = threading.Lock()


def _participant_lock(participant_id: int) -> threading.Lock:
    with _participant_locks_guard:
        lock = _participant_locks.get(participant_id)
        if lock is None:
            lock = threading.Lock()
            _participant_locks[participant_id] = lock
        return lock


def queue_depth() -> int:
    """How many requests are waiting for a slot right now (for the UI)."""
    return _limiter.waiting


# --------------------------------------------------------------------------- #
# Provider call
# --------------------------------------------------------------------------- #


# Where the key comes from, in priority order:
#   1. GEMINI_API_KEY          - local development
#   2. VCC_SECRET_ID           - AWS Secrets Manager (preferred on EC2)
#   3. VCC_SSM_PARAM           - SSM Parameter Store, SecureString
#
# On EC2 give the instance an IAM role with read access to the one secret and
# set nothing else; the key then never exists on disk, in the repo, or in the
# shell history. boto3 is imported lazily so local runs need no AWS packages.

SECRET_ID_ENV = "VCC_SECRET_ID"          # AWS Secrets Manager
KEYVAULT_URL_ENV = "VCC_KEYVAULT_URL"    # Azure Key Vault, e.g. https://x.vault.azure.net
KEYVAULT_SECRET_ENV = "VCC_KEYVAULT_SECRET"
SSM_PARAM_ENV = "VCC_SSM_PARAM"
AWS_REGION_ENV = "AWS_REGION"

_key_cache: Dict[str, str] = {}


def _fetch_aws_secret() -> Optional[str]:
    secret_id = os.environ.get(SECRET_ID_ENV, "").strip()
    ssm_param = os.environ.get(SSM_PARAM_ENV, "").strip()
    if not secret_id and not ssm_param:
        return None
    try:
        import boto3  # noqa: PLC0415 - optional, only needed on AWS
    except ImportError as exc:
        raise GatewayError(
            f"{SECRET_ID_ENV or SSM_PARAM_ENV} is set but boto3 is not installed. "
            f"Run: pip install boto3"
        ) from exc

    region = os.environ.get(AWS_REGION_ENV) or None
    try:
        if secret_id:
            client = boto3.client("secretsmanager", region_name=region)
            payload = client.get_secret_value(SecretId=secret_id)
            raw = payload.get("SecretString") or ""
            # Accept either a bare string or {"GEMINI_API_KEY": "..."}
            raw = raw.strip()
            if raw.startswith("{"):
                return str(json.loads(raw).get(API_KEY_ENV, "")).strip()
            return raw
        client = boto3.client("ssm", region_name=region)
        payload = client.get_parameter(Name=ssm_param, WithDecryption=True)
        return str(payload["Parameter"]["Value"]).strip()
    except Exception as exc:  # noqa: BLE001 - surfaced as a gateway error
        raise GatewayError(f"could not read the API key from AWS: {exc}") from exc



def _azure_token(resource: str = "https://vault.azure.net") -> str:
    """Get a managed-identity token, on either App Service or a VM.

    The two hosts expose managed identity through completely different
    endpoints, and this is not interchangeable:

      * App Service / Functions / Container Apps inject IDENTITY_ENDPOINT and
        IDENTITY_HEADER into the container. You call that local endpoint with
        the header as a shared secret.
      * A plain VM uses the IMDS address 169.254.169.254 with `Metadata: true`.

    Trying IMDS on App Service gives "[Errno 111] Connection refused", because
    nothing is listening there. Prefer the injected endpoint when present.
    """
    endpoint = os.environ.get("IDENTITY_ENDPOINT", "").strip()
    header = os.environ.get("IDENTITY_HEADER", "").strip()

    if endpoint and header:
        url = (
            f"{endpoint}?resource={urllib.parse.quote(resource, safe='')}"
            f"&api-version=2019-08-01"
        )
        request = urllib.request.Request(url, headers={"X-IDENTITY-HEADER": header})
        host = "App Service identity endpoint"
    else:
        url = (
            "http://169.254.169.254/metadata/identity/oauth2/token"
            f"?api-version=2018-02-01&resource={urllib.parse.quote(resource, safe='')}"
        )
        request = urllib.request.Request(url, headers={"Metadata": "true"})
        host = "Azure IMDS"

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))["access_token"]
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise GatewayError(
            f"{host} returned HTTP {exc.code}: {detail}. "
            f"Is a managed identity assigned to this app?"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise GatewayError(
            f"could not get a managed-identity token from {host}: {exc}. "
            f"Is a managed identity assigned to this app?"
        ) from exc


def _fetch_azure_secret() -> Optional[str]:
    """Read the API key from Azure Key Vault using the host's own identity.

    Uses the Key Vault REST API directly, so no azure-* packages are needed.
    Assign the app a managed identity with 'Key Vault Secrets User' on the
    vault and set VCC_KEYVAULT_URL + VCC_KEYVAULT_SECRET; nothing else.
    """
    vault = os.environ.get(KEYVAULT_URL_ENV, "").strip().rstrip("/")
    name = os.environ.get(KEYVAULT_SECRET_ENV, "").strip()
    if not vault or not name:
        return None

    token = _azure_token()
    secret_url = f"{vault}/secrets/{name}?api-version=7.4"
    try:
        request = urllib.request.Request(
            secret_url, headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return str(json.loads(response.read().decode("utf-8"))["value"]).strip()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise GatewayError(
            f"Key Vault returned HTTP {exc.code}: {detail}. "
            f"Does this app's identity have 'Key Vault Secrets User' on {vault}?"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise GatewayError(f"could not read the secret from Key Vault: {exc}") from exc

def _api_key() -> str:
    cached = _key_cache.get("key")
    if cached:
        return cached

    key = (
        os.environ.get(API_KEY_ENV, "").strip()
        or (_fetch_aws_secret() or "")
        or (_fetch_azure_secret() or "")
    )
    if not key:
        raise GatewayError(
            f"No API key available. Set {API_KEY_ENV} for local runs, "
            f"{SECRET_ID_ENV} / {SSM_PARAM_ENV} for AWS, or "
            f"{KEYVAULT_URL_ENV} + {KEYVAULT_SECRET_ENV} for Azure Key Vault."
        )
    _key_cache["key"] = key
    return key


def key_source() -> str:
    """For the health endpoint. Never returns the key itself."""
    if os.environ.get(API_KEY_ENV, "").strip():
        return "env:GEMINI_API_KEY"
    if os.environ.get(SECRET_ID_ENV, "").strip():
        return f"aws:secretsmanager:{os.environ[SECRET_ID_ENV]}"
    if os.environ.get(SSM_PARAM_ENV, "").strip():
        return f"aws:ssm:{os.environ[SSM_PARAM_ENV]}"
    if os.environ.get(KEYVAULT_URL_ENV, "").strip():
        return (f"azure:keyvault:{os.environ[KEYVAULT_URL_ENV]}"
                f"/{os.environ.get(KEYVAULT_SECRET_ENV, '?')}")
    return "unset"


def _call_model(user_prompt: str) -> Tuple[str, Dict[str, int]]:
    """One upstream request. Returns (text, usage). Raises GatewayError."""
    body = json.dumps(
        {
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "generationConfig": {
                "temperature": TEMPERATURE,
                "maxOutputTokens": MAX_OUTPUT_TOKENS,
                "candidateCount": 1,
            },
        }
    ).encode("utf-8")

    url = f"{API_BASE}/{MODEL}:generateContent?key={_api_key()}"

    payload = None
    last_throttle = ""
    for throttle_attempt in range(RETRY_ON_429 + 1):
        request = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with _limiter.slot():
                with urllib.request.urlopen(
                    request, timeout=REQUEST_TIMEOUT_S
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            # 429 = rate limited, 5xx = transient upstream. Back off and retry;
            # the participant is never charged for either.
            if exc.code == 429 or 500 <= exc.code < 600:
                if throttle_attempt >= RETRY_ON_429:
                    raise GatewayError(
                        f"the model is rate limited right now (HTTP {exc.code}). "
                        f"Nothing was charged - try again in a moment."
                    ) from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                try:
                    delay = float(retry_after) if retry_after else 0.0
                except (TypeError, ValueError):
                    delay = 0.0
                delay = max(delay, BACKOFF_BASE_S * (2 ** throttle_attempt))
                last_throttle = f"HTTP {exc.code}"
                time.sleep(delay)
                continue
            raise GatewayError(f"model returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GatewayError(f"could not reach the model: {exc.reason}") from exc
        except (TimeoutError, OSError) as exc:
            raise GatewayError(f"model request failed: {exc}") from exc

    if payload is None:
        raise GatewayError(f"model request failed after retries ({last_throttle})")

    usage_raw = payload.get("usageMetadata") or {}
    usage = {
        "input": int(usage_raw.get("promptTokenCount") or 0),
        "output": int(usage_raw.get("candidatesTokenCount") or 0),
        "total": int(usage_raw.get("totalTokenCount") or 0),
    }
    if not usage["total"]:
        usage["total"] = usage["input"] + usage["output"]

    candidates = payload.get("candidates") or []
    if not candidates:
        blocked = (payload.get("promptFeedback") or {}).get("blockReason")
        raise GatewayError(f"model returned no candidates (blockReason={blocked})")

    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        reason = candidates[0].get("finishReason")
        raise GatewayError(f"model returned empty text (finishReason={reason})")
    return text, usage


# --------------------------------------------------------------------------- #
# Response handling
# --------------------------------------------------------------------------- #


def extract_code(text: str) -> Optional[str]:
    match = CODE_FENCE_RE.search(text)
    code = match.group(1) if match else text
    code = code.strip()
    return code or None


def validate_code(code: str) -> Optional[str]:
    """Return an error string if the code is not a loadable policy."""
    try:
        compiled = compile(code, "<policy>", "exec")
    except SyntaxError as exc:
        return f"SyntaxError line {exc.lineno}: {exc.msg}"
    namespace: Dict[str, object] = {}
    try:
        exec(compiled, namespace)  # noqa: S102 - sandboxing is the runner's job
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__} while loading: {exc}"
    policy_cls = namespace.get("Policy")
    if policy_cls is None:
        return "no class named Policy was defined"
    if not callable(getattr(policy_cls, "decide", None)):
        return "Policy has no decide() method"
    return None


def build_user_prompt(
    participant_prompt: str, current_code: Optional[str], feedback: Optional[str]
) -> str:
    prompt = (participant_prompt or "").strip()[:MAX_PROMPT_CHARS]
    blocks = []
    if current_code:
        blocks.append(
            "The policy you are modifying:\n\n```python\n" + current_code.strip() + "\n```"
        )
    if feedback:
        blocks.append("Loading the previous attempt failed with:\n\n" + feedback)
    blocks.append("Instruction from the engineer:\n\n" + prompt)
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def generate(
    db_path: Path,
    participant_id: int,
    participant_prompt: str,
    current_code: Optional[str] = None,
) -> Generation:
    """Spend budget to produce a validated policy for one participant.

    Charges only for attempts that returned loadable code. Upstream errors
    and unloadable output are refunded, up to FREE_RETRIES extra tries.
    """
    # One in-flight request per participant: a double-click must not spend twice.
    lock = _participant_lock(participant_id)
    if not lock.acquire(timeout=MAX_QUEUE_WAIT_S):
        raise GatewayError("you already have a generation in flight")
    try:
        return _generate_locked(db_path, participant_id, participant_prompt, current_code)
    finally:
        lock.release()


def _generate_locked(
    db_path: Path,
    participant_id: int,
    participant_prompt: str,
    current_code: Optional[str] = None,
) -> Generation:
    remaining = budget_remaining(db_path, participant_id)
    if remaining <= 0:
        raise BudgetExhausted("AI budget exhausted")

    feedback: Optional[str] = None
    spent_this_call = 0
    last_error: Optional[str] = None

    for attempt in range(1, FREE_RETRIES + 2):
        user_prompt = build_user_prompt(participant_prompt, current_code, feedback)
        started = time.time()
        text, usage = _call_model(user_prompt)
        elapsed = time.time() - started

        code = extract_code(text)
        error = validate_code(code) if code else "no code block in the response"

        record_call(
            db_path,
            participant_id=participant_id,
            model=MODEL,
            temperature=TEMPERATURE,
            prompt=participant_prompt,
            response_text=text,
            code=code or "",
            input_tokens=usage["input"],
            output_tokens=usage["output"],
            charged=0 if error else usage["total"],
            attempt=attempt,
            latency_s=elapsed,
            error=error,
        )

        if error is None:
            spent_this_call += usage["total"]
            remaining = spend_budget(db_path, participant_id, usage["total"])
            return Generation(
                code=code or "",
                raw_text=text,
                input_tokens=usage["input"],
                output_tokens=usage["output"],
                total_tokens=usage["total"],
                charged=usage["total"],
                attempts=attempt,
                remaining=remaining,
                refunded=attempt > 1,
                note=(
                    f"{attempt - 1} unusable generation(s) were not charged"
                    if attempt > 1
                    else None
                ),
            )

        last_error = error
        feedback = error

    raise GatewayError(
        f"the model failed to produce loadable code in "
        f"{FREE_RETRIES + 1} attempts (last error: {last_error}). "
        f"Nothing was charged to your budget."
    )
