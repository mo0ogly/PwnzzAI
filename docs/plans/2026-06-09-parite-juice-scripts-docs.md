# Parité PwnzzAI ↔ JuiceLab — scripts + docs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring PwnzzAI's launcher/installer scripts and documentation up to the same production quality as the `/home/fpizzi/juice` reference (used with students last week): synchronized `.sh`+`.ps1`, separate prof/élève `.docx`, FR/EN parity for all docs.

**Architecture:** PwnzzAI runs as a single `docker compose` stack at repo root (3 services: `ollama`, `pwnzzai-app` :8090, `pwnzzai-coach` :8095). Unlike juice (native npm/python launch), PwnzzAI's launcher wraps `docker compose`. The teacher dashboard is the *central* JuiceLab dashboard, deployed only via `scripts/deploy-dashboard.sh` — **the student installer never touches it** (explicit user requirement).

**Tech Stack:** Bash, PowerShell 7+, Docker Compose v2, python-docx + mermaid-cli (mmdc) for `.docx`, Markdown FR/EN.

**Quality bar (from juice audit):** `set -euo pipefail`; TTY-aware color helpers (info/ok/warn/err); `-h/--help` usage; prerequisite checks (`need_cmd`); idempotent `.env` rewrite (preserve existing valid values, portable sed via tmpfile); port/health checks with timeout; clear recap block; `.sh`/`.ps1` feature-synchronized (same flags, same messages).

---

## Deliverables overview

**Scripts (repo root + scripts/):**
1. `pwnzzai.sh` + `pwnzzai.ps1` — launcher wrapping docker compose (up/down/restart/status/logs/health/models/help)
2. `scripts/install-student.sh` + `scripts/install-student.ps1` — idempotent student installer (solo + cohorte modes; never installs dashboard)
3. `scripts/deploy-dashboard.ps1` — PowerShell parity for the existing prof-only `deploy-dashboard.sh`

**Docs (FR/EN parity):**
4. `docs/STUDENT-INSTALL-FR.md` + `docs/STUDENT-INSTALL-EN.md`
5. `README_FR.md` (full mirror of `README.md`)
6. `INSTALL.md` + `INSTALL_FR.md`
7. `docs/ARCHITECTURE-EN.md` (mirror of existing FR `ARCHITECTURE.md`)

**Generated .docx (split prof/élève):**
8. `docs/build_install_guides.py` → produces `docs/GUIDE-INSTALL-ELEVE.docx` (no prof content) + `docs/GUIDE-INSTALL-PROF.docx`, adapted from `build_coach_guide.py` styling and juice's `generate_install_guides.py` structure.

---

## Task 1: Launcher `pwnzzai.sh`

**Files:**
- Create: `pwnzzai.sh` (repo root, chmod +x)

**Design:** Mirror juice.sh's helper layer (colors, `say/ok/warn/errp`, TTY guard) but every command delegates to `docker compose`. The compose file is at repo root (no `docker/` subdir).

**Commands:**
- `up` / `start` → `docker compose up -d --build` then remind to run `models`
- `down` / `stop` → `docker compose down`
- `restart` → down + up
- `status` → `docker compose ps`
- `logs [coach|app|ollama|all]` → `docker compose logs -f [svc]` (default all)
- `health` → curl `http://localhost:8095/__coach/health` (expect `"ollama": true`) + `http://localhost:8090` HTTP code
- `models` → delegate to `scripts/pull-models.sh`
- `wipe` → `docker compose down -v` (with confirmation unless `-y`)
- `help` → usage block

**Step 1: Write the script** with header usage block (lines 2–N readable via `sed` for `-h`), `set -u`, color helpers copied from juice.sh pattern, a `DC` detection (`docker compose` v2 vs `docker-compose` v1), and the dispatcher.

**Step 2: Verify**
- `bash -n pwnzzai.sh` (syntax)
- `./pwnzzai.sh help` shows usage
- `./pwnzzai.sh status` lists the 3 containers
- `./pwnzzai.sh health` → coach health JSON, app HTTP 200
- shellcheck if available: `shellcheck pwnzzai.sh`

**Step 3: Commit** `feat(scripts): pwnzzai.sh launcher wrapping docker compose`

---

## Task 2: Launcher `pwnzzai.ps1`

**Files:**
- Create: `pwnzzai.ps1` (repo root)

**Design:** Feature-synchronized with `pwnzzai.sh`. Same commands, same messages (FR), `$ErrorActionPreference='Stop'`, `Write-Host -ForegroundColor` helpers (Info cyan / Ok green / Warn yellow / Err red), `Get-DockerCompose` wrapper, param `[string]$Command='help'`, `[string]$Target='all'`, `[switch]$Yes`.

**Step 1: Write** mirroring Task 1 command-for-command. Health check via `Invoke-WebRequest`/`curl.exe`.

**Step 2: Verify** `pwsh -NoProfile -File pwnzzai.ps1 help` (if pwsh present); else manual review against `pwnzzai.sh` for flag/message parity. Document parity in commit.

**Step 3: Commit** `feat(scripts): pwnzzai.ps1 (parité PowerShell du launcher)`

---

## Task 3: `scripts/install-student.sh`

**Files:**
- Create: `scripts/install-student.sh` (chmod +x)

**Design:** Adapt juice `install-student.sh`. Key differences:
- `.env` is at **repo root** (`$ROOT/.env`), copied from `.env.example`.
- Stack is full PwnzzAI (3 services) in **all** modes — the lab *is* the coach. No per-student dashboard.
- Modes:
  - **solo** (no `-d`): `JUICELAB_DASHBOARD_URL` left empty → coach works, no reporting.
  - **cohorte** (`-d URL` or `-d HOST[:PORT]`): set `JUICELAB_DASHBOARD_URL` to the prof dashboard; push events.
- Flags: `-c|--cohort`, `-d|--dashboard HOST[:PORT]|URL`, `-l|--label`, `-y|--yes`, `--reset`, `-h|--help`. (No `--server` — students never run the dashboard.)
- Steps: prereqs (`docker`, compose) → reset if asked → ensure root `.env` from `.env.example` → set `JUICELAB_COHORT_ID` / `JUICELAB_INSTANCE_LABEL` / `JUICELAB_DASHBOARD_URL` (preserve valid existing) → `docker compose up -d --build` → `scripts/pull-models.sh` → health wait on `:8095/__coach/health` → recap (élève URL :8095, brut :8090, cohorte/label/dashboard).
- Reuse juice helpers verbatim where portable: `env_get`/`env_set` (tmpfile sed), `port_*`, `wait_http`, color helpers, `detect_lan_ip` (used only for the recap hint, not for dashboard install).
- `-d` value: accept full URL (`http://host:5000`) or bare `HOST`/`HOST:PORT` → normalize to `http://HOST:PORT` (default port 5000, matching `.env.example` default `host.docker.internal:5000`).

**Step 1: Write** the script.

**Step 2: Verify**
- `bash -n scripts/install-student.sh`
- `./scripts/install-student.sh -h` prints usage
- dry run solo on this machine: `./scripts/install-student.sh -c TEST-2026 -y` → containers up, models present, `:8095/__coach/health` ok, recap correct, `.env` has empty/!set `JUICELAB_DASHBOARD_URL`.
- idempotency: re-run → existing cohort/label preserved, no error.
- cohorte: `./scripts/install-student.sh -c TEST-2026 -d 192.168.1.10 -l poste-test -y` → `.env` `JUICELAB_DASHBOARD_URL=http://192.168.1.10:5000`, label set.
- shellcheck if available.

**Step 3: Commit** `feat(scripts): install-student.sh (solo + cohorte, sans dashboard)`

---

## Task 4: `scripts/install-student.ps1`

**Files:**
- Create: `scripts/install-student.ps1`

**Design:** Feature-synchronized with Task 3. Params `-Cohort`, `-Dashboard`, `-Label`, `-Yes`, `-Reset`. Proper `.SYNOPSIS/.DESCRIPTION/.PARAMETER` comment-based help. `Test-Token`, `Get-EnvValue`/`Set-EnvValue`, `Get-DockerCompose`, `Wait-Http`. Same recap text (FR) as the `.sh`.

**Step 1: Write** mirroring Task 3.

**Step 2: Verify** `pwsh -NoProfile -File scripts/install-student.ps1 -? ` / `Get-Help`; if no pwsh, line-by-line parity review vs `.sh` (flags, messages, .env keys). Note method in commit.

**Step 3: Commit** `feat(scripts): install-student.ps1 (parité PowerShell)`

---

## Task 5: `scripts/deploy-dashboard.ps1` (prof parity)

**Files:**
- Create: `scripts/deploy-dashboard.ps1`

**Design:** PowerShell mirror of existing `deploy-dashboard.sh` (sparse clone of juicelab dashboard+docker+scripts at pinned ref, delegate to bootstrap). Reads `.env` for `JUICELAB_REPO_URL`/`JUICELAB_DASHBOARD_REF`. Prof-only; documented as such.

**Step 1: Write.** **Step 2: Verify** `bash -n`-equivalent: `pwsh -NoProfile -Command "Get-Command -Syntax"` or review parity. **Step 3: Commit** `feat(scripts): deploy-dashboard.ps1 (parité prof)`

---

## Task 6: `docs/STUDENT-INSTALL-FR.md` + `-EN.md`

**Files:**
- Create: `docs/STUDENT-INSTALL-FR.md`, `docs/STUDENT-INSTALL-EN.md`

**Design:** Adapt juice `STUDENT-INSTALL-FR.md` (407 l.) to PwnzzAI. Sections: 0 mode picker (cohorte vs solo, **warning: élève n'installe PAS le dashboard prof**), 1 what's installed (3 containers, ports 8095/8090, ollama models, ~build time), 2 prerequisites table + sanity check, 3 one-command install (`install-student.sh`/`.ps1`, cohorte `-d` + solo), 3.3 what the installer does, 3.4 other modes table, 4 verify (`:8095` coach panel, `:8090` brut, `:8095/__coach/health`, smoke test: open lab → coach panel → hints → judge), 5 daily use (`pwnzzai.sh up/down/logs/wipe` + raw `docker compose`), 6 troubleshooting (ports 8090/8095, compose not found, perms, PowerShell policy, ollama models missing → `models`, dashboard unreachable, 401/CORS on remote dashboard), 7 uninstall, 8 help. Reference `img/coach-panel.png`. Annexe A: Docker install Linux (méthode A/B mutuellement exclusives, note arm64) — reusable from juice.
- EN = faithful translation, identical structure (parity).

**Step 1: Write FR. Step 2: Write EN. Step 3: Verify** internal links resolve, image paths exist (`docs/img/coach-panel.png` etc.), ports/URLs match `docker-compose.yml` + scripts. **Step 4: Commit** `docs: STUDENT-INSTALL FR/EN (parité juice)`

---

## Task 7: `README_FR.md`

**Files:**
- Create: `README_FR.md` (root)
- Modify: `README.md` (add a top line linking to `README_FR.md`; mirror back the EN link)

**Design:** Full French mirror of `README.md` (keep Mermaid diagrams as-is, translate prose/tables). Add reciprocal language links at top of both.

**Step 1: Write. Step 2: Verify** section parity vs `README.md`. **Step 3: Commit** `docs: README_FR.md (parité FR/EN)`

---

## Task 8: `INSTALL.md` + `INSTALL_FR.md`

**Files:**
- Create: `INSTALL.md`, `INSTALL_FR.md` (root)

**Design:** Standalone install reference extracted/elevated from README + guides. Sections: prerequisites; one-command student install (link to STUDENT-INSTALL); manual `docker compose up -d --build` + `pull-models.sh`; cohort wiring (`.env` vars); prof dashboard deploy (`deploy-dashboard.sh`/`.ps1`, prof-only); verification; teardown. EN + FR parity.

**Step 1: Write EN. Step 2: Write FR. Step 3: Verify** commands match scripts. **Step 4: Commit** `docs: INSTALL.md + INSTALL_FR.md`

---

## Task 9: `docs/ARCHITECTURE-EN.md`

**Files:**
- Create: `docs/ARCHITECTURE-EN.md`
- Modify: `docs/ARCHITECTURE.md` (add reciprocal language link line)

**Design:** Faithful English translation of existing FR `ARCHITECTURE.md` (147 l.), Mermaid kept.

**Step 1: Write. Step 2: Verify** parity. **Step 3: Commit** `docs: ARCHITECTURE-EN.md (parité FR/EN)`

---

## Task 10: `docs/build_install_guides.py` → split prof/élève .docx

**Files:**
- Create: `docs/build_install_guides.py`
- Generate: `docs/GUIDE-INSTALL-ELEVE.docx`, `docs/GUIDE-INSTALL-PROF.docx`
- (Keep existing `build_coach_guide.py` / `GUIDE-COACH-PWNZZAI.docx` as-is, or note deprecation.)

**Design:** Reuse `build_coach_guide.py`'s python-docx helpers (palette BLUE/PURPLE, `GREY_FILL/NOTE_FILL/HEAD_FILL`, heading styles, code/note boxes, table builder, `render_mermaid` via mmdc, page setup, footer page numbers) and juice `generate_install_guides.py`'s two-document structure. Produce **two** documents:
- **ELEVE**: cover, what gets installed (3 containers, :8095/:8090), prerequisites, install (cohorte/solo via `install-student`), verify + smoke test, coach panel walkthrough (screenshots: coach-closed, coach-panel, coach-hints, coach-progress), daily use, troubleshooting. **No dashboard-deploy / token / prof-ops content.**
- **PROF**: cover, role, prerequisites, cohort setup, deploy central dashboard (`deploy-dashboard.sh`/`.ps1`), distribute cohort id + dashboard URL to students, dashboard screenshots (prof-dashboard-light/dark), events emitted table, judge model selection, security, teardown.
- Shared annexes (Docker install per OS, PowerShell unlock) factored into a helper used by both.

**Step 1: Write** `build_install_guides.py` (factor common section builders; two `build_eleve(doc)` / `build_prof(doc)` functions).

**Step 2: Generate & verify**
- `python docs/build_install_guides.py` (use the existing `.venv`/mmdc setup the coach guide uses)
- both `.docx` exist, non-trivial size
- open/convert to confirm: ELEVE has **no** prof/token content; PROF has dashboard + events; screenshots embedded; Mermaid rendered; TOC/headings/page numbers present.

**Step 3: Commit** `docs: build_install_guides.py + GUIDE-INSTALL-ELEVE/PROF.docx (split prof/élève)`

---

## Task 11: Final wiring + verification

**Files:**
- Modify: `README.md` / `README_FR.md` Documentation section → link new guides, scripts, docx.
- Modify: `docs/PARITY-JUICELAB.md` → add a "scripts & docs parity" section noting the new artifacts.

**Step 1:** Update doc indexes.
**Step 2: Full verification** (REQUIRED SUB-SKILL: superpowers:verification-before-completion):
- `bash -n` + `shellcheck` on all `.sh`
- `./pwnzzai.sh health` green
- fresh `./scripts/install-student.sh -c TEST -y` from a clean `.env` → stack + models + health ok
- both `.docx` regenerate cleanly
- all FR/EN doc pairs present; internal links + image paths resolve
**Step 3: Commit** `docs: wire new scripts/guides into README + parity doc`

---

## Notes / decisions baked in
- **Student installer never deploys the dashboard** (user requirement). Prof dashboard = `deploy-dashboard.sh`/`.ps1` only, documented in PROF guide.
- All docs shipped **FR + EN** (user requirement "en anglais aussi").
- `.docx` **split** into ELEVE (no prof content) + PROF (user requirement).
- `.sh`/`.ps1` kept **feature-synchronized**; parity verified per-pair.
- `.env` lives at **repo root** for PwnzzAI (not `docker/` like juice).
