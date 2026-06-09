<#
  pwnzzai.ps1 - Launcher PwnzzAI (sidecar pedagogique OWASP PwnzzAI) - Windows

  Parite stricte avec pwnzzai.sh : memes commandes, memes messages FR.

  Contrairement a juice (process natifs npm/python), ce launcher est un WRAPPER
  fin autour de `docker compose` : toute la stack est definie dans
  docker-compose.yml a la racine du repo (3 services : ollama, pwnzzai-app,
  pwnzzai-coach).

  Entree eleve  : http://localhost:8095   (coach FastAPI = entrypoint eleve)
  PwnzzAI brut  : http://localhost:8090   (produit OWASP brut)
  Sante coach   : http://localhost:8095/__coach/health  (-> "ollama": true)

  Usage :
    .\pwnzzai.ps1 up | start            demarre la stack (build + up -d)
    .\pwnzzai.ps1 down | stop           arrete la stack
    .\pwnzzai.ps1 restart               down puis up
    .\pwnzzai.ps1 status                docker compose ps
    .\pwnzzai.ps1 logs [coach|app|ollama|all]
    .\pwnzzai.ps1 health                ping coach (JSON) + brut (code HTTP)
    .\pwnzzai.ps1 models                tire les modeles Ollama (.env)
    .\pwnzzai.ps1 wipe [-Yes]           down -v (DESTRUCTIF : supprime ollama_data)
    .\pwnzzai.ps1 help                  cet ecran

  Modele 'models' : on tire directement les modeles via
  `docker exec ollama ollama pull <model>` en lisant OLLAMA_MODEL +
  COACH_JUDGE_MODEL depuis .env (meme logique que scripts/pull-models.sh).
  Approche choisie : robuste sur Windows sans dependre d'un bash installe.
#>

[CmdletBinding()]
param(
  [string]$Command = 'help',
  [string]$Target  = 'all',
  [switch]$Yes
)

$ErrorActionPreference = 'Stop'

# ---- Constantes ------------------------------------------------------------
# On se place a la racine du repo (la ou vit docker-compose.yml) : toutes les
# commandes docker compose doivent etre lancees depuis ce dossier (parite avec
# pwnzzai.sh qui fait `cd "$ROOT"`).
$Root      = $PSScriptRoot
Set-Location -LiteralPath $Root
$CoachUrl  = 'http://localhost:8095'
$RawUrl    = 'http://localhost:8090'
$HealthUrl = "$CoachUrl/__coach/health"
$EnvFile   = Join-Path $Root '.env'

# ---- Couleurs --------------------------------------------------------------
function Say  { param([string]$m) Write-Host $m -ForegroundColor Cyan }
function Ok   { param([string]$m) Write-Host $m -ForegroundColor Green }
function Warn { param([string]$m) Write-Host $m -ForegroundColor Yellow }
function Errp { param([string]$m) Write-Host $m -ForegroundColor Red }

# ---- Detection docker compose ----------------------------------------------
# Prefere la v2 (`docker compose`), repli sur la v1 (`docker-compose`).
# Retourne un tableau d'arguments a prefixer (ex: @('docker','compose')).
function Get-DockerCompose {
  try {
    & docker compose version *> $null
    if ($LASTEXITCODE -eq 0) { return @('docker', 'compose') }
  } catch { }
  if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
    return @('docker-compose')
  }
  Errp "docker compose introuvable (ni v2 'docker compose', ni v1 'docker-compose')."
  Errp "Installe Docker Desktop ou le plugin docker compose, puis reessaie."
  exit 1
}

# Lance docker compose avec les arguments fournis.
# $dc vaut @('docker','compose') (v2) ou @('docker-compose') (v1) : on construit
# la liste complete (exe + sous-commande eventuelle + args) puis on splatte.
function Invoke-DC {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$DcArgs)
  $dc  = Get-DockerCompose
  $exe = $dc[0]
  $rest = @()
  if ($dc.Count -gt 1) { $rest = $dc[1..($dc.Count - 1)] }
  & $exe @($rest + $DcArgs)
}

# Lit une cle de .env (derniere occurrence), retire guillemets, sinon defaut.
function Get-EnvVal {
  param([string]$Key, [string]$Default)
  if (Test-Path $EnvFile) {
    $line = Select-String -Path $EnvFile -Pattern "^$([regex]::Escape($Key))=" |
            Select-Object -Last 1
    if ($line) {
      $val = ($line.Line -split '=', 2)[1].Trim().Trim('"').Trim("'")
      if ($val) { return $val }
    }
  }
  return $Default
}

# ---- Commandes -------------------------------------------------------------
function Cmd-Up {
  Say '== Demarrage de la stack PwnzzAI (docker compose up -d --build) =='
  Invoke-DC up -d --build
  Write-Host ''
  Ok 'Stack demarree.'
  Warn 'Pense a tirer les modeles Ollama (1re fois ou volume neuf) :'
  Warn '    .\pwnzzai.ps1 models'
  Write-Host ''
  Say "Eleve (coach) : $CoachUrl"
  Say "PwnzzAI brut  : $RawUrl"
}

function Cmd-Down {
  Say '== Arret de la stack PwnzzAI (docker compose down) =='
  Invoke-DC down
  Ok 'Stack arretee.'
}

function Cmd-Restart {
  Cmd-Down
  Write-Host ''
  Cmd-Up
}

function Cmd-Status {
  Say '== Status de la stack PwnzzAI =='
  Invoke-DC ps
}

function Cmd-Logs {
  param([string]$T)
  $svc = ''
  switch ($T) {
    'coach'  { $svc = 'pwnzzai-coach' }
    'app'    { $svc = 'pwnzzai-app' }
    'ollama' { $svc = 'ollama' }
    'all'    { $svc = '' }
    ''       { $svc = '' }
    default {
      Errp "logs : cible inconnue '$T' (attendu: coach|app|ollama|all)"
      return
    }
  }
  if ($svc) {
    Say "== Logs $svc (Ctrl-C pour quitter) =="
    Invoke-DC logs -f $svc
  } else {
    Say '== Logs de toute la stack (Ctrl-C pour quitter) =='
    Invoke-DC logs -f
  }
}

function Cmd-Health {
  Say '== Health checks PwnzzAI =='

  # Coach : on veut le JSON (contient "ollama": true quand les modeles sont la).
  try {
    $r = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 5 -UseBasicParsing
    Ok "  Coach   $HealthUrl  HTTP $([int]$r.StatusCode)"
    Write-Host "  $($r.Content)"
  } catch {
    $code = $null
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    if ($code) {
      Ok "  Coach   $HealthUrl  HTTP $code"
    } else {
      Errp "  Coach   $HealthUrl  KO (injoignable)"
    }
  }

  # Brut : on se contente du code HTTP.
  try {
    $r = Invoke-WebRequest -Uri $RawUrl -TimeoutSec 5 -UseBasicParsing
    Ok "  Brut    $RawUrl  HTTP $([int]$r.StatusCode)"
  } catch {
    $code = $null
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    if ($code) {
      Ok "  Brut    $RawUrl  HTTP $code"
    } else {
      Errp "  Brut    $RawUrl  KO (injoignable)"
    }
  }
}

function Cmd-Models {
  Say '== Tirage des modeles Ollama (.env) =='
  $container = if ($env:OLLAMA_CONTAINER) { $env:OLLAMA_CONTAINER } else { 'ollama' }

  # Verifie que le conteneur ollama tourne (meme garde que pull-models.sh).
  $running = & docker ps --format '{{.Names}}' 2>$null
  if ($running -notcontains $container) {
    Errp "ERREUR: conteneur '$container' pas demarre. Lance d'abord: .\pwnzzai.ps1 up"
    return
  }

  $judge = Get-EnvVal -Key 'COACH_JUDGE_MODEL' -Default 'llama3.2:3b'
  $lab   = Get-EnvVal -Key 'OLLAMA_MODEL'      -Default 'llama3.2:1b'

  # Juge d'abord (il debloque indices + verification), puis dedup.
  $pulled = @()
  foreach ($model in @($judge, $lab)) {
    if (-not $model) { continue }
    if ($pulled -contains $model) { continue }
    $pulled += $model
    Say "[pull-models] ollama pull $model"
    & docker exec $container ollama pull $model
  }

  Say '[pull-models] modeles presents dans le conteneur :'
  & docker exec $container ollama list
  Ok '[pull-models] OK. Verifie la sante du coach :'
  Write-Host "  .\pwnzzai.ps1 health   # attendu: ""ollama"": true"
}

function Cmd-Wipe {
  param([switch]$Confirmed)
  if (-not $Confirmed) {
    Warn "ATTENTION : 'wipe' lance 'docker compose down -v'."
    Warn 'Cela SUPPRIME le volume ollama_data : il faudra RE-TELECHARGER les modeles.'
    $ans = Read-Host "Taper 'oui' pour confirmer"
    if ($ans -notmatch '^(oui|OUI|o|O|yes|YES|y|Y)$') {
      Say "Annule. Rien n'a ete supprime."
      return
    }
  }
  Say '== Wipe de la stack PwnzzAI (docker compose down -v) =='
  Invoke-DC down -v
  Ok 'Stack et volumes supprimes. Relance avec : .\pwnzzai.ps1 up  puis  .\pwnzzai.ps1 models'
}

# ---- Help ------------------------------------------------------------------
function Show-Help {
  @'
pwnzzai.ps1 - Launcher PwnzzAI (wrapper docker compose) - Windows

Commandes :
  up | start                  docker compose up -d --build (+ rappel models + URLs)
  down | stop                 docker compose down
  restart                     down puis up
  status                      docker compose ps
  logs [coach|app|ollama|all] suit les logs (defaut: all)
  health                      ping coach (JSON /__coach/health) + brut (code HTTP)
  models                      tire les modeles Ollama (lit .env)
  wipe [-Yes]                 docker compose down -v (DESTRUCTIF, confirme sauf -Yes)
  help                        cet ecran

URLs :
  Eleve (coach) : http://localhost:8095
  PwnzzAI brut  : http://localhost:8090
  Sante coach   : http://localhost:8095/__coach/health   (attendu: "ollama": true)

Note : apres un premier 'up' (ou apres 'wipe'), lancer 'models' pour tirer
les modeles Ollama, sinon les indices et le juge restent indisponibles.
'@ | Write-Host
}

# ---- Dispatcher ------------------------------------------------------------
switch ($Command.ToLower()) {
  'up'      { Cmd-Up }
  'start'   { Cmd-Up }
  'down'    { Cmd-Down }
  'stop'    { Cmd-Down }
  'restart' { Cmd-Restart }
  'status'  { Cmd-Status }
  'logs'    { Cmd-Logs -T $Target }
  'health'  { Cmd-Health }
  'models'  { Cmd-Models }
  'wipe'    { Cmd-Wipe -Confirmed:$Yes }
  'help'    { Show-Help }
  '-h'      { Show-Help }
  '--help'  { Show-Help }
  default {
    Errp "commande inconnue '$Command'"
    Show-Help
    exit 1
  }
}
