"""Forward pedagogical events to the JuiceLab teacher dashboard.

Speaks the exact contract of the dashboard's public POST /api/sync:

    {
      "student_token":   <str, required>,
      "cohort_id":       <str, required>,
      "event_type":      <one of ALLOWED_EVENT_TYPES>,
      "challenge_key":   <str, optional>,
      "data":            <object, optional>,
      "client_timestamp":<ISO str, optional>
    }
    header X-Instance-Label: <label>

cohort_id and instance_label are authoritative server-side (from env), so
a student cannot spoof another cohort from the browser. The dashboard
auto-registers an unknown (cohort, token) pair as 'validated' on first
event, so no pre-enrolment call is required.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

LOGGER = logging.getLogger("coach.dashboard")

DASHBOARD_URL = os.environ.get("JUICELAB_DASHBOARD_URL", "").rstrip("/")
COHORT_ID = os.environ.get("JUICELAB_COHORT_ID", "PWNZZAI-DEFAULT")
INSTANCE_LABEL = os.environ.get("JUICELAB_INSTANCE_LABEL", "pwnzzai-default")
DASHBOARD_TIMEOUT = float(os.environ.get("COACH_DASHBOARD_TIMEOUT", "8"))

# Mirror of the dashboard's ALLOWED_EVENT_TYPES. Kept here so the coach
# rejects a bad event_type before hitting the network.
ALLOWED_EVENT_TYPES = frozenset(
    {
        "session_start",
        "session_end",
        "hint_revealed",
        "challenge_solved",
        "journal_filled",
        "quiz_completed",
        "badge_earned",
        "flag_verified",
    }
)


def is_configured() -> bool:
    return bool(DASHBOARD_URL)


async def forward_event(
    *,
    student_token: str,
    event_type: str,
    challenge_key: str | None,
    data: dict[str, Any] | None,
    client_timestamp: str | None,
) -> dict[str, Any]:
    """Post one event to the dashboard. Returns a small status dict.

    Never raises: a dashboard outage must not break the lab. The browser
    keeps its own offline queue and retries.
    """
    if event_type not in ALLOWED_EVENT_TYPES:
        return {"ok": False, "error": f"invalid event_type '{event_type}'"}
    if not student_token:
        return {"ok": False, "error": "student_token required"}
    if not DASHBOARD_URL:
        return {"ok": False, "error": "dashboard not configured", "queued": True}

    payload: dict[str, Any] = {
        "student_token": student_token,
        "cohort_id": COHORT_ID,
        "event_type": event_type,
        "data": data or {},
    }
    if challenge_key:
        payload["challenge_key"] = challenge_key
    if client_timestamp:
        payload["client_timestamp"] = client_timestamp

    headers = {
        "Content-Type": "application/json",
        "X-Instance-Label": INSTANCE_LABEL,
    }
    try:
        async with httpx.AsyncClient(timeout=DASHBOARD_TIMEOUT) as client:
            resp = await client.post(
                f"{DASHBOARD_URL}/api/sync", json=payload, headers=headers
            )
        if resp.status_code in (200, 201):
            body = resp.json()
            LOGGER.info(
                "event forwarded type=%s challenge=%s id=%s",
                event_type, challenge_key or "-", body.get("id"),
            )
            return {"ok": True, "id": body.get("id")}
        LOGGER.warning(
            "dashboard rejected event type=%s status=%s body=%s",
            event_type, resp.status_code, resp.text[:200],
        )
        return {"ok": False, "error": f"dashboard status {resp.status_code}",
                "status": resp.status_code}
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("dashboard unreachable: %s", exc)
        return {"ok": False, "error": "dashboard unreachable", "queued": True}


async def cohort_join(*, student_token: str, email: str) -> tuple[int, dict[str, Any]]:
    """Enrol a student into the cohort via the dashboard join workflow.

    cohort_id is the server-side authoritative value (env), so the student
    only supplies their email. The dashboard creates a 'pending' request the
    teacher then approves; until then the sync gate holds the student's
    events (the browser keeps its offline queue and retries).
    """
    if not DASHBOARD_URL:
        return 503, {"error": "dashboard not configured"}
    payload = {
        "cohort_id": COHORT_ID,
        "student_token": student_token,
        "email": email,
    }
    try:
        async with httpx.AsyncClient(timeout=DASHBOARD_TIMEOUT) as client:
            resp = await client.post(
                f"{DASHBOARD_URL}/api/cohort/join", json=payload,
                headers={"Content-Type": "application/json"},
            )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("cohort join failed: %s", exc)
        return 502, {"error": "dashboard unreachable"}
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        body = {"error": resp.text[:200]}
    LOGGER.info("join cohort=%s status=%s http=%s",
                COHORT_ID, body.get("status"), resp.status_code)
    return resp.status_code, body


async def student_status(*, student_token: str) -> dict[str, Any]:
    """Poll the student's enrolment status (unknown/pending/validated/rejected)."""
    if not DASHBOARD_URL:
        return {"status": "unknown", "error": "dashboard not configured"}
    url = (f"{DASHBOARD_URL}/api/student/status"
           f"?student_token={quote(student_token)}&cohort={quote(COHORT_ID)}")
    try:
        async with httpx.AsyncClient(timeout=DASHBOARD_TIMEOUT) as client:
            resp = await client.get(url)
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("student status failed: %s", exc)
        return {"status": "unknown", "error": "dashboard unreachable"}


async def fetch_proof(
    *,
    student_token: str,
    student_name: str,
    lab: dict[str, Any],
    lang: str,
) -> tuple[int, str, str]:
    """Fetch a signed lab proof from the dashboard for this student/lab.

    The dashboard owns DASHBOARD_PROOF_SECRET and signs the markdown
    (HMAC-SHA256); the coach never holds the secret. cohort_id is the
    server-side authoritative value, so a student cannot forge a proof for
    another cohort.

    Returns (status_code, body, filename). On any failure the body is a
    short plain-text message and filename is empty.
    """
    if not DASHBOARD_URL:
        return 503, "dashboard not configured", ""
    if not student_token:
        return 400, "student_token required", ""

    name = lab.get("name_fr" if lang == "fr" else "name_en", "") or lab.get("key", "")
    goal = lab.get("goal_fr" if lang == "fr" else "goal_en", "")
    params = {
        "student_token": student_token,
        "cohort": COHORT_ID,
        "key": lab.get("key", ""),
        "name": name,
        "category": lab.get("owasp", ""),
        "description": goal,
    }
    if student_name:
        params["student_name"] = student_name
    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items() if v != "")
    url = f"{DASHBOARD_URL}/api/proof?{query}"
    try:
        async with httpx.AsyncClient(timeout=DASHBOARD_TIMEOUT) as client:
            resp = await client.get(url)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("proof fetch failed: %s", exc)
        return 502, "dashboard unreachable", ""

    if resp.status_code != 200:
        LOGGER.info("proof rejected key=%s status=%s", lab.get("key"), resp.status_code)
        return resp.status_code, resp.text[:300], ""

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"pwnzzai-{lab.get('key', 'lab')}-{ts}.md"
    return 200, resp.text, filename
