#!/usr/bin/env bash
#
# deploy-dashboard.sh - deploie le dashboard prof JuiceLab central depuis cette
# machine, SANS embarquer le code eleve juice.
#
# Wrapper fin autour du bootstrap sparse de juicelab : on tire UNIQUEMENT la
# partie prof (dashboard/ + docker/) a une ref pinnee. Installer PwnzzAI ne tire
# jamais l'overlay ni le juice-shop eleve.
#
# Usage :
#   scripts/deploy-dashboard.sh [TARGET_DIR]
#
# Lit .env si present (JUICELAB_REPO_URL, JUICELAB_DASHBOARD_REF).
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-${JUICELAB_DASHBOARD_DIR:-$HERE/.juicelab-dashboard}}"

# Charger .env si present (sans ecraser l'env deja exporte).
if [ -f "$HERE/.env" ]; then
  set -a; . "$HERE/.env"; set +a
fi

REPO_URL="${JUICELAB_REPO_URL:-https://github.com/mo0ogly/juicelab.git}"
REF="${JUICELAB_DASHBOARD_REF:-main}"
BOOTSTRAP="$TARGET/scripts/bootstrap-dashboard.sh"

echo "[deploy-dashboard] source: $REPO_URL @ $REF -> $TARGET"

# 1. Premier clone sparse si besoin (le bootstrap inclut scripts/ dans son set,
#    donc une fois present il ne se supprime pas lui-meme).
if [ ! -d "$TARGET/.git" ]; then
  git clone --filter=blob:none --sparse "$REPO_URL" "$TARGET"
  git -C "$TARGET" sparse-checkout set dashboard docker scripts
  git -C "$TARGET" checkout -q "$REF"
fi

# 2. Deleguer au bootstrap officiel (source unique de la logique de deploiement).
#    Lui-meme re-set le sparse (dashboard docker scripts), fetch, checkout REF,
#    cree le .env si absent, et up le compose dashboard-only.
chmod +x "$BOOTSTRAP"
JUICELAB_REPO_URL="$REPO_URL" JUICELAB_DASHBOARD_REF="$REF" \
  "$BOOTSTRAP" "$TARGET"
