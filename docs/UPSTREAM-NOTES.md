# Upstream notes — OWASP PwnzzAI product quirks

The PwnzzAI coach is a **sidecar**: it never modifies the OWASP product (cloned at
a pinned commit, `PWNZZAI_COMMIT` in [`.env.example`](../.env.example)). The notes
below document product behaviours we observed while building the recette, plus a
ready-to-file upstream issue. They are FYI for instructors and a paper trail for
the `docs/CHALLENGE_SOLUTIONS*.md` recette.

- Upstream repo: <https://github.com/OWASP/PwnzzAI>
- Pinned commit tested: `676b9cf7e924e8a3bd9711a507887acebd2d8c52`

---

## Quirk 1 — `MODEL_PROVIDER=openai` is ignored on the `auto` path

**Where**: `application/provider_config.py::resolve_provider` + the lab routes in
`application/route.py`.

**Symptom**: with the target fully configured for a cloud provider
(`MODEL_PROVIDER=openai`, `LITELLM_MODEL=groq/openai/gpt-oss-20b`, `GROQ_API_KEY`
set, **no** `OPENAI_API_KEY`), a JSON API call that does **not** pass
`{"provider":"openai"}` is served by **Ollama**, not the configured cloud model.

**Root cause**:

```python
# route.py — every lab endpoint
preferred = (data.get("provider") or "auto").strip().lower()   # "auto" when omitted
provider  = resolve_provider(preferred=preferred, has_openai_key=bool(api_token))

# provider_config.py
def resolve_provider(preferred=None, has_openai_key=False):
    requested = (preferred or MODEL_PROVIDER).strip().lower()   # preferred="auto" wins → MODEL_PROVIDER ignored
    if requested in {"ollama", "openai"}:
        return requested
    if requested != "auto":
        requested = "auto"
    if has_openai_key:        # checks OPENAI_API_KEY / session only — NOT GROQ_API_KEY nor a configured cloud route
        return "openai"
    if ENABLE_PROVIDER_FALLBACK:
        return "ollama"        # ← configured Groq target silently falls back here
    return "openai"
```

Two compounding facts:
1. `preferred` is always truthy (`"auto"`), so `MODEL_PROVIDER` is never consulted on that path.
2. `has_openai_key` only looks at `OPENAI_API_KEY`/session, so a cloud route keyed by `GROQ_API_KEY`/`GEMINI_API_KEY`/etc. does not flip `auto` to cloud.

**Impact**: low (the bundled web UI sends `provider` explicitly via the cloud
toggle, so interactive use is unaffected). It bites **headless/API/automation**
clients and confuses operators who set the three env vars and expect cloud by
default.

**Repro** (against the pinned build):

```bash
# .env: MODEL_PROVIDER=openai, LITELLM_MODEL=groq/openai/gpt-oss-20b, GROQ_API_KEY=gsk_..., OPENAI_API_KEY empty
curl -s -b cookies -X POST :8090/api/catering-rag/query \
  -H 'Content-Type: application/json' -d '{"query":"hi"}'            # → "provider":"ollama"  (unexpected)
curl -s -b cookies -X POST :8090/api/catering-rag/query \
  -H 'Content-Type: application/json' -d '{"query":"hi","provider":"openai"}'  # → "model_type":"groq" (expected)
```

**Suggested fix** (one line, backward compatible): on the `auto` branch, honour
`MODEL_PROVIDER` and treat a configured cloud route as "has cloud":

```python
def resolve_provider(preferred=None, has_openai_key=False):
    requested = (preferred or "auto").strip().lower()     # don't let MODEL_PROVIDER be shadowed by an empty preferred only
    if requested in {"ollama", "openai"}:
        return requested
    # auto: explicit env intent first, then any configured cloud route, then key, then fallback
    if MODEL_PROVIDER in {"ollama", "openai"}:
        return MODEL_PROVIDER
    if has_openai_key or bool(resolved_litellm_model()):
        return "openai"
    return "ollama" if ENABLE_PROVIDER_FALLBACK else "openai"
```

---

## Quirk 2 — reasoning models return empty bodies at low `max_tokens`

`groq/openai/gpt-oss-20b` (and `120b`) are **reasoning** models: with a small
`max_tokens`, all the budget goes to hidden reasoning and `litellm.completion`
returns `finish_reason="length"` with **empty** `content` — an `HTTP 200` with an
empty `response`. Not a bug per se, but a foot-gun for lab endpoints that cap
`max_tokens` low. Workaround: a non-reasoning model
(`groq/llama-3.3-70b-versatile`) or a higher `max_tokens`. Already noted in
[`.env.example`](../.env.example).

---

## Quirk 3 — `/misinformation/{ollama,openai}` detection is a stub

Both routes return `has_misinformation: false` and `misinformation_detected: []`
**hardcoded** (no detection logic in `route.py`). Any recette asserting on those
flags is always-green and worthless; assert on the `response` body instead. See
the §9 entry in [CHALLENGE_SOLUTIONS.md](./CHALLENGE_SOLUTIONS.md). If upstream
intends these flags to be live, that is a separate gap worth raising.

---

## Ready-to-file upstream issue (copy/paste)

> **Title**: `MODEL_PROVIDER=openai` ignored for API calls that omit `provider` (auto path falls back to Ollama)
>
> **Repo/commit**: OWASP/PwnzzAI @ `676b9cf7e924e8a3bd9711a507887acebd2d8c52`
>
> **Description**: When the target is configured for a non-OpenAI cloud provider
> via LiteLLM (`MODEL_PROVIDER=openai`, `LITELLM_MODEL=groq/...`, `GROQ_API_KEY`
> set, `OPENAI_API_KEY` empty), any lab API call that does not pass
> `{"provider":"openai"}` is served by Ollama instead of the configured cloud
> model. The bundled web UI is unaffected (it sends `provider` explicitly), so
> this only impacts headless/API/automation use and operators expecting the env
> config to be authoritative.
>
> **Root cause**: in `application/route.py` every endpoint computes
> `preferred = (data.get("provider") or "auto")`, which is always truthy, so in
> `provider_config.resolve_provider` the expression `preferred or MODEL_PROVIDER`
> never consults `MODEL_PROVIDER`. On the `auto` branch, `has_openai_key` only
> checks `OPENAI_API_KEY`/session — it ignores `GROQ_API_KEY`/`GEMINI_API_KEY`
> and the configured `LITELLM_MODEL` route — so `ENABLE_PROVIDER_FALLBACK` sends
> the request to Ollama.
>
> **Repro**: see commands above.
>
> **Suggested fix**: on the `auto` branch, honour `MODEL_PROVIDER` and treat a
> non-empty `resolved_litellm_model()` as "cloud available" (patch above).
> Backward compatible: explicit `provider` and explicit `ollama`/`openai` keep
> their current behaviour.

*(Draft only — not submitted. File from a maintainer account against
OWASP/PwnzzAI after confirming the behaviour on the current upstream HEAD, which
may differ from the pinned commit.)*
