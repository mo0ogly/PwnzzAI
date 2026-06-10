# 📣 PwnzzAI — Student communication: challenge corrections + Groq option

*Version française : [COMMUNICATION-ELEVES.md](./COMMUNICATION-ELEVES.md).*

Ready-to-share message (chat / email).

---

## 1) Get the corrections

The corrections for all challenges are in the repo. Update your copy:

```bash
cd PwnzzAI
git pull
```

The corrections are here: **`docs/CORRECTIONS-CHALLENGES-EN.md`**
(open it in VS Code or on GitHub). For each lab: the page to open, the exact prompt
to paste, and the proof of success. Everything was **tested for real**.

## 2) Pull the Ollama models (required the first time)

```bash
./pwnzzai.sh models
```

**Why:** the labs run on local models (`llama3.2:1b` for the target, `llama3.2:3b`
for the coach and the *agentic-SQL* lab). Without this pull, the page shows
"Ollama unavailable" and nothing responds.

➡️ **Do your exercises on Ollama**: the small model holds no defense, so exploits
go through easily. It is the recommended target to **pass** the challenges.

## 3) (Optional) Enable Groq — the "cloud" target

Groq lets you see a **real** model that **does resist** some attacks (plugin SQLi,
QR): useful to understand *why a defense holds*. Not needed to pass most labs.

**a.** Create **your own** free key at <https://console.groq.com> → *API Keys*
(it starts with `gsk_`).
⚠️ **Never use someone else's / the instructor's key** — one each, kept private.

**b.** Open the **`.env`** file at the repo root and set these 3 lines:

```bash
MODEL_PROVIDER=openai
LITELLM_MODEL=groq/llama-3.3-70b-versatile
GROQ_API_KEY=gsk_YOUR_KEY_HERE
```

*(We use `llama-3.3-70b`, not `gpt-oss-20b`: the latter returned empty answers.)*
The `.env` file is **git-ignored** → your key never goes online.

**c. Restart the stack** — mandatory step:

```bash
./pwnzzai.sh restart
```

**Why restart:** Docker only reads `.env` when the containers (re)start. Until you
relaunch, the old config stays active and your key is not picked up.

## 4) Change a setting AFTER installation

All settings live in the **`.env`** file at the repo root. The rule is always the same:

> **Edit `.env` → save → restart the stack.**
> An `.env` change is **never** applied "live": Docker only re-reads the file when
> the containers (re)start.

```bash
# 1. edit the file
nano .env            # or VS Code

# 2. restart to apply
./pwnzzai.sh restart
```

**Common settings:**

| I want to… | Line in `.env` | Extra step |
|---|---|---|
| Change the labs model | `OLLAMA_MODEL=llama3.2:3b` | pull it: `./pwnzzai.sh models` **before** restart |
| Change the coach model | `COACH_JUDGE_MODEL=llama3.2:3b` | same: `./pwnzzai.sh models` |
| Switch to Groq cloud | `MODEL_PROVIDER=openai` + `LITELLM_MODEL=groq/llama-3.3-70b-versatile` + `GROQ_API_KEY=gsk_…` | personal key |
| Back to fully local | `MODEL_PROVIDER=ollama` | — |

⚠️ **If you change `OLLAMA_MODEL` to a model not yet downloaded**, run
`./pwnzzai.sh models` **before** `restart`, otherwise the page will show "model
unavailable" (Docker does not download on its own).

## 5) Resuming the next day

No need to reinstall. At the start of the session:

```bash
cd PwnzzAI
git pull              # get the latest corrections / docs
./pwnzzai.sh up       # relaunch the stack (or ./pwnzzai.sh restart if already up)
./pwnzzai.sh status   # check the 3 services are running
```

Models pulled the day before **stay** (no need to re-run `models`, unless you
changed the model in `.env`).

---

**In short:** Ollama to **win** the exercises, Groq to **understand** the defenses.
Any `.env` change → **`./pwnzzai.sh restart`**. The corrections are in
`docs/CORRECTIONS-CHALLENGES-EN.md` after a `git pull`.
