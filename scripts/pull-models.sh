#!/usr/bin/env bash
#
# pull-models.sh - telecharge les modeles Ollama dont le coach a besoin dans le
# conteneur `ollama`.
#
# Pourquoi : un volume ollama neuf ne contient AUCUN modele. Tant que les
# modeles ne sont pas presents, les indices et le juge renvoient
# "Service coach indisponible (Ollama)". A lancer une fois apres
# `docker compose up -d`.
#
# Lit OLLAMA_MODEL (assistant des labs) et COACH_JUDGE_MODEL (indices + juge)
# depuis .env, avec des defauts si absent. Idempotent : `ollama pull` ne
# re-telecharge pas un modele deja present.
#
# Usage :
#   scripts/pull-models.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
CONTAINER="${OLLAMA_CONTAINER:-ollama}"

# Lit une cle de .env (derniere occurrence), retire guillemets simples/doubles
# (\042 = " , \047 = '), sinon valeur par defaut.
env_val() {
  local key="$1" def="$2" val=""
  if [[ -f "$ENV_FILE" ]]; then
    val="$(grep -E "^${key}=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '\042\047' | tr -d '[:space:]')"
  fi
  printf '%s' "${val:-$def}"
}

LAB_MODEL="$(env_val OLLAMA_MODEL llama3.2:1b)"
JUDGE_MODEL="$(env_val COACH_JUDGE_MODEL llama3.2:3b)"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "ERREUR: conteneur '$CONTAINER' pas demarre. Lance d'abord: docker compose up -d" >&2
  exit 1
fi

# Modeles a tirer, dedupliques (le juge d'abord : c'est lui qui debloque les
# indices et la verification de reussite).
pulled=""
for model in "$JUDGE_MODEL" "$LAB_MODEL"; do
  [[ -n "$model" ]] || continue
  case " $pulled " in *" $model "*) continue ;; esac
  pulled="$pulled $model"
  echo "[pull-models] ollama pull $model"
  docker exec "$CONTAINER" ollama pull "$model"
done

echo "[pull-models] modeles presents dans le conteneur :"
docker exec "$CONTAINER" ollama list
echo "[pull-models] OK. Verifie la sante du coach :"
echo "  curl -s http://localhost:8095/__coach/health   # attendu: \"ollama\": true"
