# INSTALL

🇫🇷 Français : [INSTALL_FR.md](./INSTALL_FR.md)

Standalone install reference for the **JuiceLab Coach for PwnzzAI**. PwnzzAI ships
as a single `docker compose` stack (3 services: `ollama`, `pwnzzai-app`,
`pwnzzai-coach`). The coach is the student entry point.

> Read the [README](./README.md) first if you have not — it explains *what* this
> is. This page only covers *how to install it*. For the deep, hand-held student
> walkthrough (Windows included), see
> [docs/STUDENT-INSTALL-EN.md](./docs/STUDENT-INSTALL-EN.md).

---

## Prerequisites

| Tool | Version | Used for |
|---|---|---|
| Docker Engine | 24+ | All scenarios |
| Docker Compose plugin | v2 (`docker compose`) | All scenarios (v1 `docker-compose` also works) |
| Git | any | Cloning the repo |
| RAM | ~4 GB free for the Ollama models (`llama3.2:1b` + `llama3.2:3b`) | Hints + judge |
| Disk | ~5 GB (Docker images + Ollama models) | All |

The first build clones OWASP PwnzzAI at a pinned commit and builds the image:
allow **5–8 minutes** and a few hundred MB of download. Subsequent builds are
cached (~10 seconds).

---

## Quick start — student (one command)

The detailed student walkthrough lives in
[docs/STUDENT-INSTALL-EN.md](./docs/STUDENT-INSTALL-EN.md). The short version:

```bash
git clone https://github.com/mo0ogly/PwnzzAI.git
cd PwnzzAI

# Linux / macOS / WSL / Git Bash
./scripts/install-student.sh -c M2-IA-2026 -d 192.168.1.10

# Windows (PowerShell 7+)
.\scripts\install-student.ps1 -Cohort M2-IA-2026 -Dashboard 192.168.1.10
```

Flags (bash / PowerShell are equivalent):

| bash | PowerShell | Effect |
|---|---|---|
| `-c, --cohort` | `-Cohort` | cohort id (e.g. `M2-IA-2026`) |
| `-d, --dashboard` | `-Dashboard` | teacher dashboard, `http://host:5000`, `host`, or `host:port`. Omit → **solo** mode (no reporting) |
| `-l, --label` | `-Label` | this machine's name in the teacher matrix |
| `-y, --yes` | `-Yes` | non-interactive, accept defaults |
| `--reset` | `-Reset` | `docker compose down -v` + clean reinstall |

The script checks Docker, writes/updates `.env` (idempotent — valid existing
values are preserved), runs `docker compose up -d --build`, pulls the Ollama
models, then waits for coach health and prints the student URLs.

---

## Manual install

```bash
git clone https://github.com/mo0ogly/PwnzzAI.git
cd PwnzzAI
cp .env.example .env          # then edit cohort/dashboard settings
docker compose up -d --build  # first build: 5–8 min
./scripts/pull-models.sh      # pull Ollama models (required once)
```

Or via the launcher wrapper:

```bash
./pwnzzai.sh up        # docker compose up -d --build
./pwnzzai.sh models    # pull Ollama models (scripts/pull-models.sh)
```

A fresh `ollama` volume contains **no models**. Until `pull-models.sh` has run,
hints and the judge return "coach service unavailable (Ollama)".

---

## Cohort wiring (`.env`)

The `.env` file lives at the repo root (copied from `.env.example`).

| Key | What it does |
|---|---|
| `JUICELAB_DASHBOARD_URL` | Dashboard URL **as seen from the container**. Same machine → `http://host.docker.internal:5000`. Empty → solo mode, no reporting (the coach still works). |
| `JUICELAB_COHORT_ID` | Cohort that groups students in the teacher dashboard. |
| `JUICELAB_INSTANCE_LABEL` | This machine's name in the teacher matrix (sent as `X-Instance-Label`). |
| `OLLAMA_MODEL` | Lab assistant model (small = fast), e.g. `llama3.2:1b`. |
| `COACH_JUDGE_MODEL` | Judge/hint model. `1b` is unreliable: use `llama3.2:3b`+. |
| `PWNZZAI_COMMIT` | Pinned OWASP commit cloned at build. Bump to track upstream. |

> `host.docker.internal` lets a container reach a service on the host (here the
> teacher dashboard on the same machine). The compose file maps it to
> `host-gateway` for the coach service, so it works on Linux too.

---

## Configure an LLM provider (target)

The OWASP product is built on **LiteLLM**, so the *target* assistant (the labs'
vulnerable AI) can run on many providers with **zero code change** — pure `.env`
config. The default is local Ollama (100% offline).

**The pattern (3 vars):**

```ini
MODEL_PROVIDER=openai             # 'openai' = cloud via LiteLLM ; 'ollama' = local (default)
LITELLM_MODEL=<provider>/<model>  # routes LiteLLM to the real provider
<PROVIDER>_API_KEY=...            # provider key
```

`MODEL_PROVIDER=openai` means **"cloud via LiteLLM"**, *not* literally OpenAI.
The prefix before `/` in `LITELLM_MODEL` selects the actual provider.

| Provider | `MODEL_PROVIDER` | `LITELLM_MODEL` (example) | Key var |
|---|---|---|---|
| Ollama (local, default) | `ollama` | — (uses `OLLAMA_MODEL`) | — |
| Groq | `openai` | `groq/openai/gpt-oss-20b` | `GROQ_API_KEY` |
| OpenAI | `openai` | `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| Google Gemini | `openai` | `gemini/gemini-2.0-flash` | `GEMINI_API_KEY` |
| Anthropic | `openai` | `anthropic/claude-3-5-haiku-latest` | `ANTHROPIC_API_KEY` |

**Step by step (example: Groq):**

1. Get a key from your provider (e.g. https://console.groq.com).
2. In `.env`, set:
   ```ini
   MODEL_PROVIDER=openai
   LITELLM_MODEL=groq/openai/gpt-oss-20b
   GROQ_API_KEY=gsk_xxx
   ```
3. Restart the stack: `./pwnzzai.sh restart`.

**Scope.** Only the `openai_*` cloud labs use this backend; the `ollama_*` labs
always use local Ollama, so keep the `ollama` service running either way.

**Security.** The key lives only in `.env`, which is gitignored — **never commit
it**. The compose file passes `GROQ_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`
and `ANTHROPIC_API_KEY` through to `pwnzzai-app` (all default empty: no behavior
change when unset).

**Cost (Groq).** Roughly **1–3 EUR / morning / 10 students**. Enable
pay-as-you-go and set a spend limit on the provider console.

**Reasoning models caveat.** `gpt-oss-20b`/`gpt-oss-120b` are *reasoning* models:
with a too-small `max_tokens` they spend the budget thinking and return an
**empty** answer (`finish_reason=length`) — which looks like "the site is broken".
`gpt-oss-20b` is enough and fast; if you want zero surprises use a non-reasoning
model such as `groq/llama-3.3-70b-versatile`.

**Upstream resilience.** This requires **no modification of the OWASP product**
(LiteLLM is what does the routing) and survives upstream updates, because PwnzzAI
is cloned at a pinned commit — exactly like the rest of the sidecar.

---

## Teacher dashboard (PROF-ONLY)

**Students do NOT do this.** The central JuiceLab dashboard is deployed **once**
and serves both Juice Shop and PwnzzAI. PwnzzAI never bundles the dashboard
server — it only points at it via `JUICELAB_DASHBOARD_URL`.

To deploy it from this machine (without cloning the juice student code):

```bash
# Linux / macOS
./scripts/deploy-dashboard.sh

# Windows (PowerShell 7+)
.\scripts\deploy-dashboard.ps1
```

This sparse-pulls only the teacher part (`dashboard/` + `docker/`) of the
juicelab repo at `JUICELAB_DASHBOARD_REF`, then runs the dashboard-only compose.
Fill the secrets in the generated `.env` (`DASHBOARD_TEACHER_TOKEN`,
`DASHBOARD_PROOF_SECRET`, ≥ 16 chars) and re-run.

Anti-pattern: do not deploy a second dashboard. One instance, many clients.

---

## Verification

- Open **http://localhost:8095** — coach entry point (student).
- Open **http://localhost:8090** — raw PwnzzAI (debug, bypasses the coach).

Check coach + Ollama health:

```bash
curl -s http://localhost:8095/__coach/health
# {"ok":true,"ollama":true,"dashboard_configured":true}
```

`"ollama": true` means the models are loaded. If `false`, run
`./pwnzzai.sh models`.

One-shot health check (coach JSON + raw HTTP code):

```bash
./pwnzzai.sh health
```

---

## Lifecycle / teardown

| Launcher | Raw docker compose | Effect |
|---|---|---|
| `./pwnzzai.sh up` | `docker compose up -d --build` | build + start the stack |
| `./pwnzzai.sh down` | `docker compose down` | stop the stack (keeps volumes) |
| `./pwnzzai.sh status` | `docker compose ps` | list services |
| `./pwnzzai.sh logs [coach\|app\|ollama\|all]` | `docker compose logs -f [svc]` | follow logs |
| `./pwnzzai.sh wipe` | `docker compose down -v` | **destructive**: removes `ollama_data` (models must be re-pulled) |

`docker compose down -v` (or `./pwnzzai.sh wipe`) deletes the `ollama_data`
volume — you will have to re-run `./pwnzzai.sh models` afterwards.
