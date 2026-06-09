# INSTALLATION

🇬🇧 English : [INSTALL.md](./INSTALL.md)

Référence d'installation autonome pour le **Coach JuiceLab pour PwnzzAI**.
PwnzzAI se livre comme une unique stack `docker compose` (3 services :
`ollama`, `pwnzzai-app`, `pwnzzai-coach`). Le coach est l'entrée des élèves.

> Lis d'abord le [README](./README.md) si ce n'est pas fait — il explique *ce
> que* c'est. Cette page ne couvre que *comment l'installer*. Pour le pas-à-pas
> élève détaillé (Windows inclus), voir
> [docs/STUDENT-INSTALL-FR.md](./docs/STUDENT-INSTALL-FR.md).

---

## Prérequis

| Outil | Version | Sert à |
|---|---|---|
| Docker Engine | 24+ | Tous les scénarios |
| Plugin Docker Compose | v2 (`docker compose`) | Tous les scénarios (la v1 `docker-compose` marche aussi) |
| Git | n'importe | Cloner le repo |
| RAM | ~4 Go libres pour les modèles Ollama (`llama3.2:1b` + `llama3.2:3b`) | Indices + juge |
| Disque | ~5 Go (images Docker + modèles Ollama) | Tous |

Le premier build clone OWASP PwnzzAI à un commit pinné et construit l'image :
compter **5 à 8 minutes** et quelques centaines de Mo de téléchargement. Les
builds suivants sont mis en cache (~10 secondes).

---

## Démarrage rapide — élève (une commande)

Le pas-à-pas élève détaillé vit dans
[docs/STUDENT-INSTALL-FR.md](./docs/STUDENT-INSTALL-FR.md). La version courte :

```bash
git clone https://github.com/mo0ogly/PwnzzAI.git
cd PwnzzAI

# Linux / macOS / WSL / Git Bash
./scripts/install-student.sh -c M2-IA-2026 -d 192.168.1.10

# Windows (PowerShell 7+)
.\scripts\install-student.ps1 -Cohort M2-IA-2026 -Dashboard 192.168.1.10
```

Options (bash / PowerShell sont équivalents) :

| bash | PowerShell | Effet |
|---|---|---|
| `-c, --cohort` | `-Cohort` | identifiant de cohorte (ex. `M2-IA-2026`) |
| `-d, --dashboard` | `-Dashboard` | dashboard prof, `http://host:5000`, `host`, ou `host:port`. Omis → mode **solo** (aucune remontée) |
| `-l, --label` | `-Label` | nom de cette machine dans la matrice prof |
| `-y, --yes` | `-Yes` | non interactif, accepte les défauts |
| `--reset` | `-Reset` | `docker compose down -v` + réinstallation propre |

Le script vérifie Docker, écrit/met à jour `.env` (idempotent — les valeurs
valides existantes sont préservées), lance `docker compose up -d --build`, tire
les modèles Ollama, puis attend la santé du coach et affiche les URLs élève.

---

## Installation manuelle

```bash
git clone https://github.com/mo0ogly/PwnzzAI.git
cd PwnzzAI
cp .env.example .env          # puis éditer les réglages cohorte/dashboard
docker compose up -d --build  # premier build : 5–8 min
./scripts/pull-models.sh      # tirer les modèles Ollama (requis une fois)
```

Ou via le wrapper launcher :

```bash
./pwnzzai.sh up        # docker compose up -d --build
./pwnzzai.sh models    # tire les modèles Ollama (scripts/pull-models.sh)
```

Un volume `ollama` neuf ne contient **aucun modèle**. Tant que
`pull-models.sh` n'a pas tourné, les indices et le juge renvoient « Service
coach indisponible (Ollama) ».

---

## Câblage cohorte (`.env`)

Le fichier `.env` vit à la racine du repo (copié depuis `.env.example`).

| Clé | Rôle |
|---|---|
| `JUICELAB_DASHBOARD_URL` | URL du dashboard **telle que vue depuis le conteneur**. Même machine → `http://host.docker.internal:5000`. Vide → mode solo, aucune remontée (le coach marche quand même). |
| `JUICELAB_COHORT_ID` | Cohorte qui regroupe les élèves dans le dashboard prof. |
| `JUICELAB_INSTANCE_LABEL` | Nom de cette machine dans la matrice prof (envoyé comme `X-Instance-Label`). |
| `OLLAMA_MODEL` | Modèle assistant des labs (petit = rapide), ex. `llama3.2:1b`. |
| `COACH_JUDGE_MODEL` | Modèle juge/indices. `1b` non fiable : utiliser `llama3.2:3b`+. |
| `PWNZZAI_COMMIT` | Commit OWASP pinné cloné au build. Bumper pour suivre l'amont. |

> `host.docker.internal` permet à un conteneur d'atteindre un service de l'hôte
> (ici le dashboard prof sur la même machine). Le fichier compose le mappe sur
> `host-gateway` pour le service coach, donc ça marche aussi sous Linux.

---

## Dashboard prof (RÉSERVÉ AU PROF)

**Les élèves ne font PAS ça.** Le dashboard JuiceLab central se déploie **une
seule fois** et sert à la fois Juice Shop et PwnzzAI. PwnzzAI n'embarque jamais
le serveur du dashboard — il pointe seulement dessus via
`JUICELAB_DASHBOARD_URL`.

Pour le déployer depuis cette machine (sans cloner le code élève juice) :

```bash
# Linux / macOS
./scripts/deploy-dashboard.sh

# Windows (PowerShell 7+)
.\scripts\deploy-dashboard.ps1
```

Cela tire en sparse uniquement la partie prof (`dashboard/` + `docker/`) du repo
juicelab à la ref `JUICELAB_DASHBOARD_REF`, puis lance le compose dashboard-only.
Renseigne les secrets dans le `.env` généré (`DASHBOARD_TEACHER_TOKEN`,
`DASHBOARD_PROOF_SECRET`, ≥ 16 caractères) puis relance.

Anti-pattern : ne déploie pas un second dashboard. Une instance, plusieurs clients.

---

## Vérification

- Ouvrir **http://localhost:8095** — entrée coach (élève).
- Ouvrir **http://localhost:8090** — PwnzzAI brut (debug, contourne le coach).

Vérifier la santé coach + Ollama :

```bash
curl -s http://localhost:8095/__coach/health
# {"ok":true,"ollama":true,"dashboard_configured":true}
```

`"ollama": true` signifie que les modèles sont chargés. Si `false`, lancer
`./pwnzzai.sh models`.

Vérification en une commande (JSON coach + code HTTP brut) :

```bash
./pwnzzai.sh health
```

---

## Cycle de vie / arrêt

| Launcher | docker compose brut | Effet |
|---|---|---|
| `./pwnzzai.sh up` | `docker compose up -d --build` | build + démarre la stack |
| `./pwnzzai.sh down` | `docker compose down` | arrête la stack (garde les volumes) |
| `./pwnzzai.sh status` | `docker compose ps` | liste les services |
| `./pwnzzai.sh logs [coach\|app\|ollama\|all]` | `docker compose logs -f [svc]` | suit les logs |
| `./pwnzzai.sh wipe` | `docker compose down -v` | **destructif** : supprime `ollama_data` (modèles à re-tirer) |

`docker compose down -v` (ou `./pwnzzai.sh wipe`) supprime le volume
`ollama_data` — il faudra relancer `./pwnzzai.sh models` ensuite.
