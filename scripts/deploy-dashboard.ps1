<#
  deploy-dashboard.ps1 - deploie le dashboard prof JuiceLab central depuis cette
  machine, SANS embarquer le code eleve juice. (Windows / PowerShell)

  Parite stricte avec scripts/deploy-dashboard.sh : memes sources, memes refs,
  meme resolution de TARGET, meme sparse-checkout (dashboard docker scripts).

  PROF UNIQUEMENT. Les eleves ne lancent JAMAIS ce script : il ne tire que la
  partie prof (dashboard/ + docker/ + scripts/) a une ref pinnee. Installer
  PwnzzAI ne tire jamais l'overlay ni le juice-shop eleve.

  Usage :
    .\scripts\deploy-dashboard.ps1 [TargetDir]

  Lit .env a la racine du repo si present (JUICELAB_REPO_URL,
  JUICELAB_DASHBOARD_REF).

  Delegation au bootstrap (bootstrap-dashboard.sh) :
    Le bootstrap officiel du dashboard est un script BASH (le dashboard lui-meme
    est Linux/Docker). Windows n'a pas bash par defaut, donc :
      - si `bash` est disponible (WSL, Git-Bash), on l'invoque exactement comme
        la version .sh, avec JUICELAB_REPO_URL / JUICELAB_DASHBOARD_REF exportes ;
      - sinon, on affiche un message clair invitant le prof a lancer le bootstrap
        sous WSL ou Git-Bash (le clone sparse, lui, est deja fait via git).
#>

[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [string]$TargetDir
)

$ErrorActionPreference = 'Stop'

# ---- Racine du repo (un cran au-dessus de scripts/) ------------------------
# Parite avec : HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
$Here = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

# ---- Resolution de TARGET --------------------------------------------------
# Parite avec : TARGET="${1:-${JUICELAB_DASHBOARD_DIR:-$HERE/.juicelab-dashboard}}"
if ($TargetDir) {
  $Target = $TargetDir
} elseif ($env:JUICELAB_DASHBOARD_DIR) {
  $Target = $env:JUICELAB_DASHBOARD_DIR
} else {
  $Target = Join-Path $Here '.juicelab-dashboard'
}

# ---- Lecture .env ----------------------------------------------------------
# Parite avec : if [ -f "$HERE/.env" ]; then set -a; . "$HERE/.env"; set +a; fi
# Attention : `set -a; . .env` SOURCE le fichier, donc une valeur dans .env
# ECRASE la variable deja presente dans l'environnement (le commentaire FR du .sh
# qui dit l'inverse est trompeur ; on suit le comportement reel du code).
# Precedence fidele au .sh : .env > env courant > defaut.
# On lit juste les deux cles utiles, derniere occurrence, quotes/espaces retires.
function Get-EnvVal {
  param([string]$Key, [string]$Default)
  $envFile = Join-Path $Here '.env'
  if (Test-Path -LiteralPath $envFile) {
    $line = Select-String -Path $envFile -Pattern "^$([regex]::Escape($Key))=" |
            Select-Object -Last 1
    if ($line) {
      $val = ($line.Line -split '=', 2)[1].Trim().Trim('"').Trim("'")
      if ($val) { return $val }
    }
  }
  # Pas de valeur dans .env : on retombe sur l'env courant, puis le defaut.
  $envVal = [Environment]::GetEnvironmentVariable($Key)
  if ($envVal) { return $envVal }
  return $Default
}

$RepoUrl = Get-EnvVal -Key 'JUICELAB_REPO_URL' -Default 'https://github.com/mo0ogly/juicelab.git'
$Ref     = Get-EnvVal -Key 'JUICELAB_DASHBOARD_REF' -Default 'main'
$Bootstrap = Join-Path (Join-Path $Target 'scripts') 'bootstrap-dashboard.sh'

Write-Host "[deploy-dashboard] source: $RepoUrl @ $Ref -> $Target"

# ---- 1. Premier clone sparse si besoin -------------------------------------
# Parite avec le bloc `if [ ! -d "$TARGET/.git" ]` : on tire UNIQUEMENT
# dashboard docker scripts a la ref pinnee.
if (-not (Test-Path -LiteralPath (Join-Path $Target '.git'))) {
  & git clone --filter=blob:none --sparse $RepoUrl $Target
  if ($LASTEXITCODE -ne 0) { throw "git clone a echoue (code $LASTEXITCODE)" }
  & git -C $Target sparse-checkout set dashboard docker scripts
  if ($LASTEXITCODE -ne 0) { throw "git sparse-checkout a echoue (code $LASTEXITCODE)" }
  & git -C $Target checkout -q $Ref
  if ($LASTEXITCODE -ne 0) { throw "git checkout '$Ref' a echoue (code $LASTEXITCODE)" }
}

# ---- 2. Deleguer au bootstrap officiel (source unique de verite) -----------
# Lui-meme re-set le sparse (dashboard docker scripts), fetch, checkout REF,
# cree le .env si absent, et up le compose dashboard-only.
# Le bootstrap est un script BASH -> il faut un bash pour l'executer.
$bash = Get-Command bash -ErrorAction SilentlyContinue
if (-not $bash) {
  Write-Host ''
  Write-Host "[deploy-dashboard] bash introuvable sur cette machine Windows." -ForegroundColor Yellow
  Write-Host "Le clone sparse est fait, mais le bootstrap officiel est un script bash" -ForegroundColor Yellow
  Write-Host "(le dashboard est Linux/Docker). Lance-le manuellement sous WSL ou Git-Bash :" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "    JUICELAB_REPO_URL='$RepoUrl' JUICELAB_DASHBOARD_REF='$Ref' \"
  Write-Host "      bash '$Bootstrap' '$Target'"
  Write-Host ""
  Write-Host "Astuce : installe WSL (wsl --install) ou Git for Windows (fournit Git-Bash)." -ForegroundColor Yellow
  exit 1
}

# bash present : on reproduit fidelement la version .sh (vars exportees + appel).
# Le .sh fait `set -a; . "$HERE/.env"; set +a`, qui exporte TOUTES les cles de
# .env vers le bootstrap (pas seulement les deux utiles). On fait pareil ici
# pour une vraie parite : on lit chaque KEY=VALUE de .env et on l'exporte.
$envFile = Join-Path $Here '.env'
if (Test-Path -LiteralPath $envFile) {
  foreach ($l in (Get-Content -LiteralPath $envFile)) {
    if ($l -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
      $env:"$($Matches[1])" = $Matches[2].Trim().Trim('"').Trim("'")
    }
  }
}
# Les deux cles documentees gagnent sur d'eventuelles valeurs vides de .env.
$env:JUICELAB_REPO_URL      = $RepoUrl
$env:JUICELAB_DASHBOARD_REF = $Ref
& $bash.Source $Bootstrap $Target
if ($LASTEXITCODE -ne 0) { throw "bootstrap-dashboard.sh a echoue (code $LASTEXITCODE)" }
