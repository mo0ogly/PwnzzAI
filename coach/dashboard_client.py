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
from typing import Any

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
