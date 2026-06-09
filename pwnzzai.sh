#!/usr/bin/env bash
#
# pwnzzai.sh - Launcher PwnzzAI (sidecar pedagogique OWASP PwnzzAI) - Linux/macOS
#
# Contrairement a juice.sh (qui lance des process natifs npm/python), ce
# launcher est un WRAPPER fin autour de `docker compose` : toute la stack est
# definie dans docker-compose.yml a la racine du repo (3 services : ollama,
# pwnzzai-app, pwnzzai-coach).
#
# Entree eleve  : http://localhost:8095   (coach FastAPI = entrypoint eleve)
# PwnzzAI brut  : http://localhost:8090   (produit OWASP brut)
# Sante coach   : http://localhost:8095/__coach/health  (-> "ollama": true)
#
# Usage :
#   ./pwnzzai.sh up | start            demarre la stack (build + up -d)
#   ./pwnzzai.sh down | stop           arrete la stack
#   ./pwnzzai.sh restart               down puis up
#   ./pwnzzai.sh status                docker compose ps
#   ./pwnzzai.sh logs [coach|app|ollama|all]
#   ./pwnzzai.sh health                ping coach (JSON) + brut (code HTTP)
#   ./pwnzzai.sh models                tire les modeles Ollama (.env)
#   ./pwnzzai.sh wipe [-y]             down -v (DESTRUCTIF : supprime ollama_data)
#   ./pwnzzai.sh help                  cet ecran
#
set -u

# ---- Constantes ------------------------------------------------------------
# On se place a la racine du repo (la ou vit docker-compose.yml) : toutes les
# commandes docker compose doivent etre lancees depuis ce dossier.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1

COACH_URL='http://localhost:8095'
RAW_URL='http://localhost:8090'
HEALTH_URL="$COACH_URL/__coach/health"
PULL_SCRIPT="$ROOT/scripts/pull-models.sh"

# ---- Couleurs (desactivees hors TTY) ---------------------------------------
if [ -t 1 ]; then
  C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'; C_YEL=$'\033[33m'; C_RED=$'\033[31m'; C_RST=$'\033[0m'
else
  C_CYAN=''; C_GREEN=''; C_YEL=''; C_RED=''; C_RST=''
fi
say()  { printf "%s%s%s\n" "$C_CYAN"  "$*" "$C_RST"; }
ok()   { printf "%s%s%s\n" "$C_GREEN" "$*" "$C_RST"; }
warn() { printf "%s%s%s\n" "$C_YEL"   "$*" "$C_RST"; }
errp() { printf "%s%s%s\n" "$C_RED"   "$*" "$C_RST" >&2; }

# ---- Detection docker compose ----------------------------------------------
# Prefere la v2 (`docker compose`), repli sur la v1 (`docker-compose`).
DC=""
detect_dc() {
  if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DC="docker-compose"
  else
    errp "docker compose introuvable (ni v2 'docker compose', ni v1 'docker-compose')."
    errp "Installe Docker Desktop ou le plugin docker compose, puis reessaie."
    exit 1
  fi
}

# ---- Commandes -------------------------------------------------------------
cmd_up() {
  say "== Demarrage de la stack PwnzzAI (docker compose up -d --build) =="
  # shellcheck disable=SC2086
  $DC up -d --build
  echo
  ok "Stack demarree."
  warn "Pense a tirer les modeles Ollama (1re fois ou volume neuf) :"
  warn "    ./pwnzzai.sh models"
  echo
  say "Eleve (coach) : $COACH_URL"
  say "PwnzzAI brut  : $RAW_URL"
}

cmd_down() {
  say "== Arret de la stack PwnzzAI (docker compose down) =="
  # shellcheck disable=SC2086
  $DC down
  ok "Stack arretee."
}

cmd_restart() {
  cmd_down
  echo
  cmd_up
}

cmd_status() {
  say "== Status de la stack PwnzzAI =="
  # shellcheck disable=SC2086
  $DC ps
}

cmd_logs() {
  local target="${1:-all}" svc=""
  case "$target" in
    coach)  svc="pwnzzai-coach" ;;
    app)    svc="pwnzzai-app" ;;
    ollama) svc="ollama" ;;
    all|"") svc="" ;;
    *)
      errp "logs : cible inconnue '$target' (attendu: coach|app|ollama|all)"
      return 1
      ;;
  esac
  if [ -n "$svc" ]; then
    say "== Logs $svc (Ctrl-C pour quitter) =="
    # shellcheck disable=SC2086
    $DC logs -f "$svc"
  else
    say "== Logs de toute la stack (Ctrl-C pour quitter) =="
    # shellcheck disable=SC2086
    $DC logs -f
  fi
}

cmd_health() {
  say "== Health checks PwnzzAI =="
  if ! command -v curl >/dev/null 2>&1; then
    warn "curl introuvable : health check impossible."
    warn "Verifie manuellement : $HEALTH_URL  et  $RAW_URL"
    return 1
  fi

  # Coach : on veut le JSON (contient \"ollama\": true quand les modeles sont la).
  local body code
  body="$(curl -s --max-time 5 "$HEALTH_URL" || true)"
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$HEALTH_URL" || true)"
  if [ -n "$body" ] && [ "$code" != "000" ] && [ -n "$code" ]; then
    ok "  Coach   $HEALTH_URL  HTTP $code"
    printf '  %s\n' "$body"
  else
    errp "  Coach   $HEALTH_URL  KO (injoignable)"
  fi

  # Brut : on se contente du code HTTP.
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$RAW_URL" || true)"
  if [ -n "$code" ] && [ "$code" != "000" ]; then
    ok "  Brut    $RAW_URL  HTTP $code"
  else
    errp "  Brut    $RAW_URL  KO (injoignable)"
  fi
}

cmd_models() {
  if [ ! -f "$PULL_SCRIPT" ]; then
    errp "Script introuvable : $PULL_SCRIPT"
    return 1
  fi
  say "== Tirage des modeles Ollama (scripts/pull-models.sh) =="
  chmod +x "$PULL_SCRIPT" 2>/dev/null || true
  bash "$PULL_SCRIPT"
}

cmd_wipe() {
  local yes="${1:-no}"
  if [ "$yes" != "-y" ] && [ "$yes" != "--yes" ]; then
    warn "ATTENTION : 'wipe' lance 'docker compose down -v'."
    warn "Cela SUPPRIME le volume ollama_data : il faudra RE-TELECHARGER les modeles."
    printf "%sTaper 'oui' pour confirmer : %s" "$C_YEL" "$C_RST"
    local ans=""
    read -r ans || true
    case "$ans" in
      oui|OUI|o|O|yes|YES|y|Y) ;;
      *) say "Annule. Rien n'a ete supprime."; return 0 ;;
    esac
  fi
  say "== Wipe de la stack PwnzzAI (docker compose down -v) =="
  # shellcheck disable=SC2086
  $DC down -v
  ok "Stack et volumes supprimes. Relance avec : ./pwnzzai.sh up  puis  ./pwnzzai.sh models"
}

# ---- Help ------------------------------------------------------------------
show_help() {
  # Bloc d'aide lisible aussi via : sed -n '...' pwnzzai.sh
  cat <<'EOF'
pwnzzai.sh - Launcher PwnzzAI (wrapper docker compose) - Linux/macOS

Commandes :
  up | start                  docker compose up -d --build (+ rappel models + URLs)
  down | stop                 docker compose down
  restart                     down puis up
  status                      docker compose ps
  logs [coach|app|ollama|all] suit les logs (defaut: all)
  health                      ping coach (JSON /__coach/health) + brut (code HTTP)
  models                      tire les modeles Ollama via scripts/pull-models.sh
  wipe [-y]                   docker compose down -v (DESTRUCTIF, confirme sauf -y)
  help                        cet ecran

URLs :
  Eleve (coach) : http://localhost:8095
  PwnzzAI brut  : http://localhost:8090
  Sante coach   : http://localhost:8095/__coach/health   (attendu: "ollama": true)

Note : apres un premier 'up' (ou apres 'wipe'), lancer 'models' pour tirer
les modeles Ollama, sinon les indices et le juge restent indisponibles.
EOF
}

# ---- Dispatcher ------------------------------------------------------------
cmd="${1:-help}"
shift 2>/dev/null || true
case "${cmd,,}" in
  up|start)        detect_dc; cmd_up ;;
  down|stop)       detect_dc; cmd_down ;;
  restart)         detect_dc; cmd_restart ;;
  status)          detect_dc; cmd_status ;;
  logs)            detect_dc; cmd_logs "${1:-all}" ;;
  health)          cmd_health ;;
  models)          cmd_models ;;
  wipe)            detect_dc; cmd_wipe "${1:-no}" ;;
  help|-h|--help)  show_help ;;
  *)
    errp "commande inconnue '$cmd'"
    show_help
    exit 1
    ;;
esac
