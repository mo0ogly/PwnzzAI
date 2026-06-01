"""JuiceLab Coach — transparent reverse proxy in front of OWASP PwnzzAI.

Design goal: leave the OWASP product 100% untouched. This sidecar sits in
front of PwnzzAI, forwards every request unchanged, and only:

  1. injects a <script>/<link> pair into HTML responses so the coach
     sidebar loads in the student's browser;
  2. serves its own API under /__coach/*:
       GET  /__coach/config   cohort + labs catalogue for the sidebar
       POST /__coach/hint     adaptive hint via Ollama          (reframe 4)
       POST /__coach/judge    LLM-as-judge of the transcript    (reframe 1)
       POST /__coach/event    forward an event to the dashboard (cohort link)
       GET  /__coach/health   coach + ollama + dashboard status
       GET  /__coach/static/* sidebar assets (coach.js, coach.css)

Transcript capture (reframe 3) happens in the browser (coach.js monkey-
patches fetch), so the proxy needs no per-lab knowledge.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

import dashboard_client as dash
import llm_judge

logging.basicConfig(
    level=os.environ.get("COACH_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
LOGGER = logging.getLogger("coach.proxy")

UPSTREAM = os.environ.get("PWNZZAI_UPSTREAM", "http://pwnzzai-app:8080").rstrip("/")
HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"

def _load_json(name: str, key: str) -> dict[str, Any]:
    """Load a data file's top-level section, tolerating absence."""
    path = HERE / name
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh).get(key, {})


with (HERE / "labs.json").open(encoding="utf-8") as fh:
    LABS: list[dict[str, Any]] = json.load(fh)["labs"]
# longest 'match' first so /data-poisoning/catering-rag beats /data-poisoning
LABS.sort(key=lambda lab_: len(lab_["match"]), reverse=True)
LABS_BY_KEY = {lab_["key"]: lab_ for lab_ in LABS}

BRIEFINGS: dict[str, Any] = _load_json("briefing.json", "briefings")
QUIZ: dict[str, Any] = _load_json("quiz.json", "quiz")

# Headers that must not be copied verbatim when proxying.
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "content-encoding",
    "content-length",
}

# coach.js is split into modules (kept under the 800-line rule). Order matters:
# i18n + state + api before the UI orchestrator. defer preserves order.
_COACH_SCRIPTS = (
    "coach-i18n.js", "coach-state.js", "coach-api.js", "coach.js",
)
INJECT_SNIPPET = (
    '<link rel="stylesheet" href="/__coach/static/coach.css">'
    '<script>window.__COACH_BASE__="/__coach";</script>'
    + "".join(
        f'<script src="/__coach/static/{s}" defer></script>'
        for s in _COACH_SCRIPTS
    )
)

app = FastAPI(title="JuiceLab Coach for PwnzzAI", docs_url=None, redoc_url=None)


# --------------------------------------------------------------------------
# Coach API
# --------------------------------------------------------------------------

@app.get("/__coach/health")
async def coach_health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "ollama": await llm_judge.healthcheck(),
            "dashboard_configured": dash.is_configured(),
        }
    )


@app.get("/__coach/config")
async def coach_config() -> JSONResponse:
    """Everything the sidebar needs to bootstrap. No secrets exposed."""
    public_labs = [
        {
            "key": lab_["key"],
            "match": lab_["match"],
            "owasp": lab_.get("owasp", ""),
            "name_fr": lab_.get("name_fr", ""),
            "name_en": lab_.get("name_en", ""),
            "goal_fr": lab_.get("goal_fr", ""),
            "goal_en": lab_.get("goal_en", ""),
            "concepts": BRIEFINGS.get(lab_["key"], {}).get("concepts", []),
            "quiz_count": len(QUIZ.get(lab_["key"], [])),
        }
        for lab_ in LABS
    ]
    return JSONResponse(
        {
            "cohort_id": dash.COHORT_ID,
            "instance_label": dash.INSTANCE_LABEL,
            "dashboard_configured": dash.is_configured(),
            "hint_cost_by_level": llm_judge.HINT_COST_BY_LEVEL,
            "labs": public_labs,
        }
    )


@app.get("/__coach/quiz/questions")
async def coach_quiz_questions(lab_key: str = "") -> JSONResponse:
    """Quiz questions for a lab, with correct answers and explanations
    STRIPPED so the browser cannot read the key. Scoring is server-side."""
    questions = QUIZ.get(lab_key)
    if not questions:
        return JSONResponse({"error": "no quiz for this lab"}, status_code=404)
    stripped = [
        {
            "question_fr": q.get("question_fr", ""),
            "question_en": q.get("question_en", ""),
            "options_fr": q.get("options_fr", []),
            "options_en": q.get("options_en", []),
        }
        for q in questions
    ]
    return JSONResponse({"lab_key": lab_key, "questions": stripped})


@app.post("/__coach/quiz/score")
async def coach_quiz_score(req: Request) -> JSONResponse:
    """Grade quiz answers. Body: {lab_key, answers:[int,...]}. Returns the
    score (0-100), per-question correctness and explanations."""
    body = await _json_body(req)
    lab_key = str(body.get("lab_key", ""))
    questions = QUIZ.get(lab_key)
    if not questions:
        return JSONResponse({"error": "no quiz for this lab"}, status_code=404)
    answers = body.get("answers") or []
    if not isinstance(answers, list):
        return JSONResponse({"error": "answers must be a list"}, status_code=400)

    lang = "fr" if str(body.get("lang", "fr")).lower().startswith("fr") else "en"
    per_q: list[dict[str, Any]] = []
    correct_count = 0
    for i, q in enumerate(questions):
        given = answers[i] if i < len(answers) else None
        ok = given == q.get("correct")
        if ok:
            correct_count += 1
        per_q.append({
            "correct": q.get("correct"),
            "given": given,
            "ok": ok,
            "explanation": q.get(f"explanation_{lang}", ""),
        })
    score = round(correct_count / len(questions) * 100) if questions else 0
    return JSONResponse({
        "lab_key": lab_key, "score": score,
        "correct_count": correct_count, "total": len(questions),
        "by_question": per_q,
    })


@app.post("/__coach/hint")
async def coach_hint(req: Request) -> JSONResponse:
    body = await _json_body(req)
    lab = LABS_BY_KEY.get(str(body.get("lab_key", "")))
    if lab is None:
        return JSONResponse({"error": "unknown lab_key"}, status_code=400)
    try:
        result = await llm_judge.hint(
            lab=lab,
            transcript=body.get("transcript") or [],
            level=body.get("level", 1),
            lang=body.get("lang", "fr"),
        )
        return JSONResponse(result)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("hint failed: %s", exc)
        return JSONResponse({"error": "hint engine unavailable"}, status_code=503)


@app.post("/__coach/judge")
async def coach_judge(req: Request) -> JSONResponse:
    body = await _json_body(req)
    lab = LABS_BY_KEY.get(str(body.get("lab_key", "")))
    if lab is None:
        return JSONResponse({"error": "unknown lab_key"}, status_code=400)
    transcript = body.get("transcript") or []
    if not transcript:
        return JSONResponse(
            {"error": "empty transcript", "success": False,
             "reason": "Aucun echange a evaluer. Discute d'abord avec l'assistant."},
            status_code=400,
        )
    try:
        result = await llm_judge.judge(lab=lab, transcript=transcript)
        return JSONResponse(result)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("judge failed: %s", exc)
        return JSONResponse({"error": "judge unavailable"}, status_code=503)


@app.post("/__coach/walkthrough")
async def coach_walkthrough(req: Request) -> JSONResponse:
    """Return the lab walkthrough (corrige) ONLY if the transcript proves the
    student succeeded. The success gate is server-side: the client's local
    'solved' flag is spoofable, so we re-judge here before revealing the
    solution, mirroring JuiceLab's solved-gated walkthrough."""
    body = await _json_body(req)
    lab = LABS_BY_KEY.get(str(body.get("lab_key", "")))
    if lab is None:
        return JSONResponse({"error": "unknown lab_key"}, status_code=400)
    transcript = body.get("transcript") or []
    if not transcript:
        return JSONResponse(
            {"error": "empty transcript", "success": False}, status_code=400
        )
    lang = "fr" if str(body.get("lang", "fr")).lower().startswith("fr") else "en"
    try:
        verdict = await llm_judge.judge(lab=lab, transcript=transcript)
        if not verdict.get("success"):
            return JSONResponse(
                {"error": "solve_first", "success": False,
                 "reason": verdict.get("reason", "")},
                status_code=403,
            )
        walkthrough = await llm_judge.debrief(lab=lab, transcript=transcript, lang=lang)
        return JSONResponse({"success": True, "walkthrough": walkthrough})
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("walkthrough failed: %s", exc)
        return JSONResponse({"error": "walkthrough unavailable"}, status_code=503)


@app.post("/__coach/event")
async def coach_event(req: Request) -> JSONResponse:
    body = await _json_body(req)
    result = await dash.forward_event(
        student_token=str(body.get("student_token", "")).strip(),
        event_type=str(body.get("event_type", "")).strip(),
        challenge_key=body.get("challenge_key"),
        data=body.get("data") if isinstance(body.get("data"), dict) else {},
        client_timestamp=body.get("client_timestamp"),
    )
    status = 201 if result.get("ok") else 202
    return JSONResponse(result, status_code=status)


@app.get("/__coach/proof")
async def coach_proof(
    lab_key: str = "", student_token: str = "", student_name: str = "", lang: str = "fr"
) -> Response:
    """Relay a signed lab proof from the dashboard as a markdown download.

    The dashboard signs (HMAC-SHA256) and the coach only forwards: no
    secret lives here. A proof exists only once the dashboard has received
    the lab's challenge_solved event.
    """
    lab = LABS_BY_KEY.get(lab_key)
    if lab is None:
        return JSONResponse({"error": "unknown lab_key"}, status_code=400)
    lang = "fr" if str(lang).lower().startswith("fr") else "en"
    status, body, filename = await dash.fetch_proof(
        student_token=student_token.strip(),
        student_name=student_name.strip(),
        lab=lab,
        lang=lang,
    )
    if status != 200:
        return JSONResponse({"error": body}, status_code=status)
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@app.get("/__coach/static/{filename}")
async def coach_static(filename: str) -> Response:
    safe = Path(filename).name  # strip any path traversal
    target = STATIC_DIR / safe
    if not target.is_file():
        return Response(status_code=404)
    media = "application/javascript" if safe.endswith(".js") else (
        "text/css" if safe.endswith(".css") else "application/octet-stream"
    )
    return FileResponse(target, media_type=media)


async def _json_body(req: Request) -> dict[str, Any]:
    try:
        data = await req.json()
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


# --------------------------------------------------------------------------
# Transparent reverse proxy (everything that is not /__coach/*)
# --------------------------------------------------------------------------

@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def proxy(path: str, request: Request) -> Response:
    url = f"{UPSTREAM}/{path}"
    # Force identity encoding upstream so HTML bodies arrive uncompressed
    # and are cheap to inject into.
    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "host"
    }
    fwd_headers["accept-encoding"] = "identity"
    body = await request.body()

    client = httpx.AsyncClient(timeout=None, follow_redirects=False)
    try:
        upstream_req = client.build_request(
            request.method, url, headers=fwd_headers,
            params=request.query_params, content=body,
        )
        upstream_resp = await client.send(upstream_req, stream=True)
    except httpx.ConnectError:
        await client.aclose()
        return JSONResponse(
            {"error": "PwnzzAI upstream unreachable", "upstream": UPSTREAM},
            status_code=502,
        )

    content_type = upstream_resp.headers.get("content-type", "")
    resp_headers = {
        k: v for k, v in upstream_resp.headers.items()
        if k.lower() not in HOP_BY_HOP
    }

    # HTML: buffer fully and inject the sidebar loader, then close.
    if "text/html" in content_type.lower():
        raw = await upstream_resp.aread()
        await upstream_resp.aclose()
        await client.aclose()
        html = _inject(raw.decode("utf-8", errors="replace"))
        return Response(
            content=html, status_code=upstream_resp.status_code,
            headers=resp_headers, media_type=content_type,
        )

    # Everything else (JSON, SSE, static, downloads): stream straight through.
    async def body_stream():
        try:
            async for chunk in upstream_resp.aiter_raw():
                yield chunk
        finally:
            await upstream_resp.aclose()
            await client.aclose()

    return StreamingResponse(
        body_stream(), status_code=upstream_resp.status_code,
        headers=resp_headers, media_type=content_type or None,
    )


def _inject(html: str) -> str:
    """Insert the coach loader once, before </head>, falling back to
    </body> then plain append. Idempotent within a single response."""
    if "/__coach/static/coach.js" in html:
        return html
    for needle in ("</head>", "</HEAD>"):
        if needle in html:
            return html.replace(needle, INJECT_SNIPPET + needle, 1)
    for needle in ("</body>", "</BODY>"):
        if needle in html:
            return html.replace(needle, INJECT_SNIPPET + needle, 1)
    return html + INJECT_SNIPPET
