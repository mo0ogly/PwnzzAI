#!/usr/bin/env bash
# PwnzzAI — installateur eleve (Linux/macOS).
#
# PwnzzAI tourne comme UNE seule stack docker compose a la racine du repo
# (3 services : ollama, pwnzzai-app, pwnzzai-coach). L'eleve lance TOUJOURS la
# stack complete : le coach EST le lab. Ce script ne deploie JAMAIS le dashboard
# prof (cela reste le role du prof via scripts/deploy-dashboard.sh).
#
# Usage :
#   ./scripts/install-student.sh                       # solo : coach local, aucune remontee
#   ./scripts/install-student.sh -c M2-IA-2026         # cohorte_id en argument
#   ./scripts/install-student.sh -y                    # non interactif, accepte les defauts
#   ./scripts/install-student.sh --reset               # docker compose down -v + reinstall propre
#
# Deux modes (seule difference : la remontee des events vers un dashboard prof) :
#   (defaut)  solo     : JUICELAB_DASHBOARD_URL vide -> le coach marche en local,
#                        aucune remontee.
#   -d VALUE  cohorte  : JUICELAB_DASHBOARD_URL renseigne -> les events sont
#                        pousses vers le dashboard prof. VALUE accepte :
#                          http://host:5000   (URL complete, gardee telle quelle)
#                          host               (-> http://host:5000)
#                          host:5050          (-> http://host:5050)
#
# Scenario cohorte (Juice/PwnzzAI chez l'eleve, dashboard consolide chez le prof) :
#   Cote eleve :
#     ./scripts/install-student.sh -d 192.168.1.10 -l amelie -c M2-IA-2026
#       -> lance la stack PwnzzAI complete, configuree pour pousser ses events
#          vers le dashboard du prof (http://192.168.1.10:5000).
#   Cote prof :
#     le dashboard central est deploye separement (scripts/deploy-dashboard.sh) ;
#     ce script eleve ne le touche jamais.
#
# Ce script :
#   1. verifie docker / docker compose
#   2. cree la racine .env depuis .env.example si absente
#   3. ecrit / met a jour les cles JUICELAB_* (les valeurs valides existantes ne
#      sont PAS ecrasees)
#   4. lance la stack complete (docker compose up -d --build)
#   5. tire les modeles Ollama (scripts/pull-models.sh)
#   6. attend la sante du coach, puis affiche les URLs eleve
#
# Idempotent : re-executer le script ne casse rien ni n'ecrase les valeurs
# valides deja presentes dans .env.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
ENV_EXAMPLE="${ROOT}/.env.example"
PULL_SCRIPT="${ROOT}/scripts/pull-models.sh"

COACH_URL='http://localhost:8095'
RAW_URL='http://localhost:8090'
HEALTH_URL='http://127.0.0.1:8095/__coach/health'
DEFAULT_DASHBOARD_PORT=5000   # aligne sur .env.example

COHORT_ID=""
INSTANCE_LABEL=""
DASHBOARD_VALUE=""     # -d : URL / host / host:port du dashboard prof (mode cohorte)
ASSUME_YES=0
RESET=0

# ---- args ------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--cohort)    COHORT_ID="${2:-}"; shift 2 ;;
        -d|--dashboard) DASHBOARD_VALUE="${2:-}"; shift 2 ;;
        -l|--label)     INSTANCE_LABEL="${2:-}"; shift 2 ;;
        -y|--yes)       ASSUME_YES=1; shift ;;
        --reset)        RESET=1; shift ;;
        -h|--help)
            sed -n '2,43p' "$0"
            exit 0
            ;;
        *) echo "Argument inconnu : $1" >&2; exit 2 ;;
    esac
done

# ---- helpers ---------------------------------------------------------------

C_INFO='\033[1;36m'; C_OK='\033[1;32m'; C_WARN='\033[1;33m'; C_ERR='\033[1;31m'; C_OFF='\033[0m'
say()  { printf "${C_INFO}==>${C_OFF} %s\n" "$*"; }
ok()   { printf "${C_OK}OK${C_OFF}  %s\n" "$*"; }
warn() { printf "${C_WARN}!!! ${C_OFF}%s\n" "$*"; }
die()  { printf "${C_ERR}!!! ${C_OFF}%s\n" "$*" >&2; exit 1; }

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Outil manquant : $1. Installe-le avant de relancer."
}

prompt() {
    local question="$1" default="${2:-}" reply
    if [[ "${ASSUME_YES}" -eq 1 ]]; then
        echo "${default}"; return
    fi
    if [[ -n "${default}" ]]; then
        read -r -p "${question} [${default}] : " reply
        echo "${reply:-${default}}"
    else
        read -r -p "${question} : " reply
        echo "${reply}"
    fi
}

# Une valeur .env est consideree valide si elle est non vide et n'est pas un
# placeholder du .env.example (les valeurs de .env.example sont de vrais defauts,
# pas des "replace-me", donc on garde juste le garde non-vide ici).
is_value_valid() {
    [[ -n "${1:-}" ]]
}

env_get() {
    local key="$1"
    [[ -f "${ENV_FILE}" ]] || { echo ""; return; }
    # Derniere occurrence, on retire l'eventuel CR final (fichiers edites sous Windows).
    awk -F= -v k="${key}" '$1==k { sub(/^[^=]*=/,""); val=$0 } END { sub(/\r$/,"",val); print val }' "${ENV_FILE}"
}

# Reecriture portable de .env (GNU sed != BSD sed) via fichier temporaire.
# Cree la cle si absente, la remplace sinon. La valeur peut etre vide.
env_set() {
    local key="$1" val="$2" tmp
    if [[ -f "${ENV_FILE}" ]] && grep -q "^${key}=" "${ENV_FILE}" 2>/dev/null; then
        tmp="$(mktemp "${ENV_FILE}.XXXXXX")"
        # Delimiteur | et val echappe pour ne pas casser sur les URLs (http://...).
        local esc="${val//\\/\\\\}"; esc="${esc//|/\\|}"; esc="${esc//&/\\&}"
        sed "s|^${key}=.*|${key}=${esc}|" "${ENV_FILE}" > "${tmp}" && mv "${tmp}" "${ENV_FILE}"
    else
        printf '%s=%s\n' "${key}" "${val}" >> "${ENV_FILE}"
    fi
}

# Normalise la valeur -d en URL complete :
#   http://x:5000 ou https://...  -> garde telle quelle
#   host                          -> http://host:<DEFAULT_DASHBOARD_PORT>
#   host:5050                     -> http://host:5050
normalize_dashboard_url() {
    local v="$1"
    case "$v" in
        http://*|https://*) printf '%s' "$v" ;;
        *:*)                printf 'http://%s' "$v" ;;
        *)                  printf 'http://%s:%s' "$v" "${DEFAULT_DASHBOARD_PORT}" ;;
    esac
}

# Detection de l'IP LAN (Linux hostname -I, repli macOS ipconfig/ifconfig) ;
# utilisee uniquement pour l'astuce du recap.
detect_lan_ip() {
    local ip iface
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [[ -z "${ip}" ]] && command -v ipconfig >/dev/null 2>&1; then
        for iface in en0 en1 en2 en3; do
            ip="$(ipconfig getifaddr "${iface}" 2>/dev/null)"
            [[ -n "${ip}" ]] && break
        done
    fi
    if [[ -z "${ip}" ]] && command -v ifconfig >/dev/null 2>&1; then
        ip="$(ifconfig 2>/dev/null | awk '/inet /{ if ($2 != "127.0.0.1") { print $2; exit } }')"
    fi
    echo "${ip}"
}

wait_http() {
    local url="$1" name="$2" timeout="${3:-120}" elapsed=0
    while (( elapsed < timeout )); do
        if curl -fsS --max-time 3 "${url}" >/dev/null 2>&1; then
            ok "${name} : ${url}"
            return 0
        fi
        sleep 3; elapsed=$((elapsed + 3))
    done
    warn "${name} pas encore pret apres ${timeout}s : ${url}"
    return 1
}

# ---- Step 0 : prereqs ------------------------------------------------------

say "Verification des prerequis"
need_cmd docker
need_cmd awk
need_cmd sed

if docker compose version >/dev/null 2>&1; then
    DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    DC=(docker-compose)
else
    die "docker compose v2 (ou docker-compose v1) introuvable. Installe Docker Desktop ou le plugin docker compose."
fi
ok "docker, ${DC[*]} disponibles"

[[ -f "${ENV_EXAMPLE}" ]] || die ".env.example introuvable : ${ENV_EXAMPLE}"

# ---- Step 1 : reset si demande --------------------------------------------

if [[ "${RESET}" -eq 1 ]]; then
    say "--reset : docker compose down -v (efface les volumes, dont ollama_data)"
    (cd "${ROOT}" && "${DC[@]}" down -v 2>/dev/null || true)
    # Reinitialise les cles eleve pour repartir des defauts .env.example.
    if [[ -f "${ENV_FILE}" ]]; then
        for key in JUICELAB_COHORT_ID JUICELAB_INSTANCE_LABEL JUICELAB_DASHBOARD_URL; do
            def="$(awk -F= -v k="${key}" '$1==k { sub(/^[^=]*=/,""); val=$0 } END { sub(/\r$/,"",val); print val }' "${ENV_EXAMPLE}")"
            env_set "${key}" "${def}"
        done
    fi
    ok "Etat precedent supprime (cles eleve reinitialisees aux defauts)"
fi

# ---- Step 2 : .env racine --------------------------------------------------

if [[ ! -f "${ENV_FILE}" ]]; then
    say "Creation de .env a partir de .env.example"
    cp "${ENV_EXAMPLE}" "${ENV_FILE}"
fi

# ---- Step 3 : cles JUICELAB_* ----------------------------------------------

# JUICELAB_COHORT_ID : -c, sinon valeur existante valide, sinon prompt (defaut M2-IA-2026).
if [[ -z "${COHORT_ID}" ]]; then
    CURRENT_COHORT="$(env_get JUICELAB_COHORT_ID)"
    if is_value_valid "${CURRENT_COHORT}"; then
        COHORT_ID="${CURRENT_COHORT}"
        ok "JUICELAB_COHORT_ID deja configure : ${COHORT_ID}"
    else
        COHORT_ID="$(prompt 'Identifiant de cohorte (ex M2-IA-2026)' 'M2-IA-2026')"
    fi
fi
env_set JUICELAB_COHORT_ID "${COHORT_ID}"
ok "JUICELAB_COHORT_ID = ${COHORT_ID}"

# JUICELAB_INSTANCE_LABEL : -l, sinon valeur existante valide, sinon hostname / id -un.
if [[ -z "${INSTANCE_LABEL}" ]]; then
    CURRENT_LABEL="$(env_get JUICELAB_INSTANCE_LABEL)"
    if is_value_valid "${CURRENT_LABEL}"; then
        INSTANCE_LABEL="${CURRENT_LABEL}"
        ok "JUICELAB_INSTANCE_LABEL deja configure : ${INSTANCE_LABEL}"
    else
        INSTANCE_LABEL="$(hostname 2>/dev/null || id -un 2>/dev/null || echo pwnzzai-poste)"
    fi
fi
env_set JUICELAB_INSTANCE_LABEL "${INSTANCE_LABEL}"
ok "JUICELAB_INSTANCE_LABEL = ${INSTANCE_LABEL}"

# JUICELAB_DASHBOARD_URL : -d normalise (cohorte), sinon solo -> vide.
if [[ -n "${DASHBOARD_VALUE}" ]]; then
    DASHBOARD_URL="$(normalize_dashboard_url "${DASHBOARD_VALUE}")"
    env_set JUICELAB_DASHBOARD_URL "${DASHBOARD_URL}"
    MODE="cohorte"
    ok "Mode cohorte : JUICELAB_DASHBOARD_URL = ${DASHBOARD_URL} (events pousses vers le prof)"
else
    env_set JUICELAB_DASHBOARD_URL ""
    DASHBOARD_URL=""
    MODE="solo"
    ok "Mode solo : JUICELAB_DASHBOARD_URL vide (coach local, aucune remontee)"
fi

# ---- Step 4 : build + up (stack complete, TOUJOURS) ------------------------

say "docker compose up -d --build (premier build : 5-8 min, builds suivants : ~10s)"
(cd "${ROOT}" && "${DC[@]}" up -d --build)
ok "Stack PwnzzAI lancee (ollama + pwnzzai-app + pwnzzai-coach)"

# ---- Step 5 : modeles Ollama ----------------------------------------------

if [[ -f "${PULL_SCRIPT}" ]]; then
    say "Tirage des modeles Ollama (scripts/pull-models.sh)"
    chmod +x "${PULL_SCRIPT}" 2>/dev/null || true
    bash "${PULL_SCRIPT}" || warn "Le tirage des modeles a echoue ou est incomplet. Relancer : ./pwnzzai.sh models"
else
    warn "scripts/pull-models.sh introuvable : tirer les modeles a la main (./pwnzzai.sh models)."
fi

# ---- Step 6 : health check -------------------------------------------------

say "Attente de la sante du coach (timeout 120s)"
wait_http "${HEALTH_URL}" "Coach /__coach/health" 120 || \
    warn "Le coach n'a pas repondu a temps. Verifier les logs : ./pwnzzai.sh logs coach"

# En mode cohorte, verification best-effort du dashboard prof (LAN/firewall
# peuvent bloquer : on previent, on n'echoue pas).
if [[ "${MODE}" == "cohorte" && -n "${DASHBOARD_URL}" ]]; then
    if curl -fsS --max-time 3 "${DASHBOARD_URL}" >/dev/null 2>&1; then
        ok "Dashboard prof joignable depuis l'hote : ${DASHBOARD_URL}"
    else
        # Port reel = celui de l'URL normalisee (pas DASHBOARD_VALUE qui peut etre
        # un host nu sans port -> on retomberait sur DEFAULT_DASHBOARD_PORT).
        hostport="${DASHBOARD_URL#*://}"; hostport="${hostport%%/*}"
        case "${hostport}" in *:*) DASHBOARD_PORT="${hostport##*:}" ;; *) DASHBOARD_PORT="${DEFAULT_DASHBOARD_PORT}" ;; esac
        warn "Dashboard prof ${DASHBOARD_URL} injoignable depuis l'hote (best-effort)."
        warn "Note : le coach vise cette URL DEPUIS le conteneur ; verifier que le prof a"
        warn "deploye le dashboard, que le LAN est plat, et le firewall (port ${DASHBOARD_PORT})."
    fi
fi

# ---- Step 7 : recap --------------------------------------------------------

LAN_IP="$(detect_lan_ip)"; LAN_IP="${LAN_IP:-<ip-de-cette-machine>}"

echo
echo "========================================================================"
printf "${C_OK}Installation OK (mode %s)${C_OFF}\n\n" "${MODE}"

cat <<EOF
  La stack PwnzzAI complete tourne sur cette machine (le coach EST le lab).

  Eleve  -> ${COACH_URL}        (entrypoint coach : labs + indices + juge)
  Brut   -> ${RAW_URL}        (PwnzzAI OWASP brut, sans coach)
  Sante  -> ${HEALTH_URL}   (attendu: "ollama": true)

  Cohorte           : ${COHORT_ID}
  Instance (label)  : ${INSTANCE_LABEL}
EOF

if [[ "${MODE}" == "cohorte" ]]; then
    cat <<EOF
  Dashboard prof    : ${DASHBOARD_URL}   (events pousses depuis le coach)
EOF
else
    cat <<EOF
  Dashboard prof    : (aucun) - mode solo, le coach marche en local.
                      Pour rejoindre une cohorte : relancer avec -d <ip-prof>
                      ex : ./scripts/install-student.sh -d ${LAN_IP} -c ${COHORT_ID}
EOF
fi

cat <<EOF

  Stop  : ./pwnzzai.sh down        (ou : ${DC[*]} down)
  Wipe  : ./pwnzzai.sh wipe        (DESTRUCTIF : ${DC[*]} down -v)
  Logs  : ./pwnzzai.sh logs        (ou : ${DC[*]} logs -f)

  Idempotent : relancer ce script ne casse rien et preserve les valeurs valides
  deja presentes dans .env.
========================================================================
EOF
