<#
.SYNOPSIS
  PwnzzAI - installateur eleve (Windows). Parite stricte avec install-student.sh.

.DESCRIPTION
  PwnzzAI tourne comme UNE seule stack docker compose a la racine du repo
  (3 services : ollama, pwnzzai-app, pwnzzai-coach). L'eleve lance TOUJOURS la
  stack complete : le coach EST le lab. Ce script ne deploie JAMAIS le dashboard
  prof (cela reste le role du prof via scripts/deploy-dashboard.sh).

  Deux modes (seule difference : la remontee des events vers un dashboard prof) :
    (defaut)     solo    : JUICELAB_DASHBOARD_URL vide -> coach local, aucune remontee.
    -Dashboard   cohorte : JUICELAB_DASHBOARD_URL renseigne -> events pousses vers
                           le dashboard prof. La valeur accepte :
                             http://host:5000  (URL complete, gardee telle quelle)
                             host              (-> http://host:5000)
                             host:5050         (-> http://host:5050)

  Ce script :
    1. verifie docker / docker compose
    2. cree la racine .env depuis .env.example si absente
    3. ecrit / met a jour les cles JUICELAB_* (valeurs valides preservees)
    4. lance la stack complete (docker compose up -d --build)
    5. tire les modeles Ollama (scripts/pull-models.sh si bash dispo, sinon
       docker exec ollama ollama pull, meme logique que pull-models.sh)
    6. attend la sante du coach, puis affiche les URLs eleve

  Idempotent : re-executer le script ne casse rien ni n'ecrase les valeurs
  valides deja presentes dans .env.

.PARAMETER Cohort
  Identifiant de cohorte (ex M2-IA-2026). Alias -c.

.PARAMETER Dashboard
  URL / host / host:port du dashboard prof -> bascule en mode cohorte. Alias -d.

.PARAMETER Label
  Nom de ce poste dans la matrice prof (defaut : nom de la machine). Alias -l.

.PARAMETER Yes
  Non interactif : accepte les defauts sans poser de question. Alias -y.

.PARAMETER Reset
  docker compose down -v puis reinstall propre (reinitialise les cles eleve).

.EXAMPLE
  .\scripts\install-student.ps1
  Mode solo : coach local, aucune remontee.

.EXAMPLE
  .\scripts\install-student.ps1 -Dashboard 192.168.1.10 -Label amelie -Cohort M2-IA-2026
  Mode cohorte : stack complete + events pousses vers http://192.168.1.10:5000.
#>

[CmdletBinding()]
param(
  [Alias('c')][string]$Cohort,
  [Alias('d')][string]$Dashboard,
  [Alias('l')][string]$Label,
  [Alias('y')][switch]$Yes,
  [switch]$Reset
)

$ErrorActionPreference = 'Stop'

# ---- Constantes ------------------------------------------------------------
$Root        = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$EnvFile     = Join-Path $Root '.env'
$EnvExample  = Join-Path $Root '.env.example'
$PullScript  = Join-Path $Root 'scripts/pull-models.sh'

$CoachUrl    = 'http://localhost:8095'
$RawUrl      = 'http://localhost:8090'
$HealthUrl   = 'http://127.0.0.1:8095/__coach/health'
$DefaultDashboardPort = 5000   # aligne sur .env.example

# ---- Couleurs --------------------------------------------------------------
function Say  { param([string]$m) Write-Host "==> $m" -ForegroundColor Cyan }
function Ok   { param([string]$m) Write-Host "OK  $m" -ForegroundColor Green }
function Warn { param([string]$m) Write-Host "!!! $m" -ForegroundColor Yellow }
function Die  { param([string]$m) Write-Host "!!! $m" -ForegroundColor Red; exit 1 }

function Test-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    Die "Outil manquant : $Name. Installe-le avant de relancer."
  }
}

function Prompt-Value {
  param([string]$Question, [string]$Default)
  if ($Yes) { return $Default }
  if ($Default) {
    $reply = Read-Host "$Question [$Default]"
    if ([string]::IsNullOrWhiteSpace($reply)) { return $Default }
    return $reply
  }
  return (Read-Host $Question)
}

# Valide : non vide (les defauts .env.example sont de vrais defauts, pas des placeholders).
function Test-EnvValue { param([string]$v) return -not [string]::IsNullOrWhiteSpace($v) }

# Lit une cle de .env (derniere occurrence), retire CR final et guillemets.
function Get-EnvValue {
  param([string]$Key, [string]$File = $EnvFile)
  if (-not (Test-Path $File)) { return '' }
  $line = Select-String -Path $File -Pattern "^$([regex]::Escape($Key))=" |
          Select-Object -Last 1
  if (-not $line) { return '' }
  $val = ($line.Line -split '=', 2)[1]
  return $val.TrimEnd("`r").Trim().Trim('"').Trim("'")
}

# Reecriture idempotente de .env : remplace la cle si presente, l'ajoute sinon.
# La valeur peut etre vide. Preserve les autres lignes telles quelles.
function Set-EnvValue {
  param([string]$Key, [string]$Value)
  if (-not (Test-Path $EnvFile)) { Set-Content -LiteralPath $EnvFile -Value '' -NoNewline }
  $lines = @(Get-Content -LiteralPath $EnvFile)
  $pattern = "^$([regex]::Escape($Key))="
  $found = $false
  $out = foreach ($l in $lines) {
    if ($l -match $pattern) { $found = $true; "$Key=$Value" } else { $l }
  }
  if (-not $found) { $out = @($out) + "$Key=$Value" }
  Set-Content -LiteralPath $EnvFile -Value $out
}

# Normalise -Dashboard en URL complete (parite avec normalize_dashboard_url du .sh).
function ConvertTo-DashboardUrl {
  param([string]$v)
  if ($v -match '^https?://') { return $v }
  if ($v -match ':')          { return "http://$v" }
  return "http://${v}:$DefaultDashboardPort"
}

# Detection docker compose v2 / v1. Retourne un tableau d'args.
function Get-DockerCompose {
  try { & docker compose version *> $null; if ($LASTEXITCODE -eq 0) { return @('docker','compose') } } catch { }
  if (Get-Command docker-compose -ErrorAction SilentlyContinue) { return @('docker-compose') }
  Die "docker compose v2 (ou docker-compose v1) introuvable. Installe Docker Desktop ou le plugin docker compose."
}

function Invoke-DC {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$DcArgs)
  $dc = Get-DockerCompose
  $exe = $dc[0]
  $rest = if ($dc.Count -gt 1) { $dc[1..($dc.Count-1)] } else { @() }
  Push-Location -LiteralPath $Root
  try { & $exe @($rest + $DcArgs) } finally { Pop-Location }
}

function Get-LanIp {
  try {
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
          Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.PrefixOrigin -ne 'WellKnown' } |
          Select-Object -First 1 -ExpandProperty IPAddress
    if ($ip) { return $ip }
  } catch { }
  return '<ip-de-cette-machine>'
}

function Wait-Http {
  param([string]$Url, [string]$Name, [int]$TimeoutSec = 120)
  $elapsed = 0
  while ($elapsed -lt $TimeoutSec) {
    try {
      Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing *> $null
      Ok "${Name} : $Url"
      return $true
    } catch { }
    Start-Sleep -Seconds 3; $elapsed += 3
  }
  Warn "$Name pas encore pret apres ${TimeoutSec}s : $Url"
  return $false
}

# ---- Step 0 : prereqs ------------------------------------------------------

Say 'Verification des prerequis'
Test-Command docker
$DcArr = Get-DockerCompose
Ok "docker, $($DcArr -join ' ') disponibles"

if (-not (Test-Path $EnvExample)) { Die ".env.example introuvable : $EnvExample" }

# ---- Step 1 : reset si demande --------------------------------------------

if ($Reset) {
  Say '--reset : docker compose down -v (efface les volumes, dont ollama_data)'
  try { Invoke-DC down -v } catch { }
  if (Test-Path $EnvFile) {
    foreach ($key in @('JUICELAB_COHORT_ID','JUICELAB_INSTANCE_LABEL','JUICELAB_DASHBOARD_URL')) {
      Set-EnvValue -Key $key -Value (Get-EnvValue -Key $key -File $EnvExample)
    }
  }
  Ok 'Etat precedent supprime (cles eleve reinitialisees aux defauts)'
}

# ---- Step 2 : .env racine --------------------------------------------------

if (-not (Test-Path $EnvFile)) {
  Say 'Creation de .env a partir de .env.example'
  Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
}

# ---- Step 3 : cles JUICELAB_* ----------------------------------------------

# JUICELAB_COHORT_ID
$cohortVal = $Cohort
if (-not $cohortVal) {
  $current = Get-EnvValue -Key 'JUICELAB_COHORT_ID'
  if (Test-EnvValue $current) {
    $cohortVal = $current
    Ok "JUICELAB_COHORT_ID deja configure : $cohortVal"
  } else {
    $cohortVal = Prompt-Value -Question 'Identifiant de cohorte (ex M2-IA-2026)' -Default 'M2-IA-2026'
  }
}
Set-EnvValue -Key 'JUICELAB_COHORT_ID' -Value $cohortVal
Ok "JUICELAB_COHORT_ID = $cohortVal"

# JUICELAB_INSTANCE_LABEL
$labelVal = $Label
if (-not $labelVal) {
  $current = Get-EnvValue -Key 'JUICELAB_INSTANCE_LABEL'
  if (Test-EnvValue $current) {
    $labelVal = $current
    Ok "JUICELAB_INSTANCE_LABEL deja configure : $labelVal"
  } else {
    $labelVal = if ($env:COMPUTERNAME) { $env:COMPUTERNAME } else { 'pwnzzai-poste' }
  }
}
Set-EnvValue -Key 'JUICELAB_INSTANCE_LABEL' -Value $labelVal
Ok "JUICELAB_INSTANCE_LABEL = $labelVal"

# JUICELAB_DASHBOARD_URL
if ($Dashboard) {
  $dashboardUrl = ConvertTo-DashboardUrl $Dashboard
  Set-EnvValue -Key 'JUICELAB_DASHBOARD_URL' -Value $dashboardUrl
  $Mode = 'cohorte'
  Ok "Mode cohorte : JUICELAB_DASHBOARD_URL = $dashboardUrl (events pousses vers le prof)"
} else {
  Set-EnvValue -Key 'JUICELAB_DASHBOARD_URL' -Value ''
  $dashboardUrl = ''
  $Mode = 'solo'
  Ok 'Mode solo : JUICELAB_DASHBOARD_URL vide (coach local, aucune remontee)'
}

# ---- Step 4 : build + up (stack complete, TOUJOURS) ------------------------

Say 'docker compose up -d --build (premier build : 5-8 min, builds suivants : ~10s)'
Invoke-DC up -d --build
Ok 'Stack PwnzzAI lancee (ollama + pwnzzai-app + pwnzzai-coach)'

# ---- Step 5 : modeles Ollama ----------------------------------------------

Say 'Tirage des modeles Ollama'
$bash = Get-Command bash -ErrorAction SilentlyContinue
if ($bash -and (Test-Path $PullScript)) {
  # Reutilise scripts/pull-models.sh si bash dispo (source unique de verite).
  & $bash.Source $PullScript
  if ($LASTEXITCODE -ne 0) { Warn 'Le tirage des modeles a echoue ou est incomplet. Relancer : .\pwnzzai.ps1 models' }
} else {
  # Repli sans bash : meme logique que pull-models.sh (juge d'abord, dedup).
  $container = if ($env:OLLAMA_CONTAINER) { $env:OLLAMA_CONTAINER } else { 'ollama' }
  $running = & docker ps --format '{{.Names}}' 2>$null
  if ($running -notcontains $container) {
    Warn "Conteneur '$container' pas demarre : tirer les modeles plus tard via .\pwnzzai.ps1 models"
  } else {
    $judge = Get-EnvValue -Key 'COACH_JUDGE_MODEL'; if (-not $judge) { $judge = 'llama3.2:3b' }
    $lab   = Get-EnvValue -Key 'OLLAMA_MODEL';      if (-not $lab)   { $lab   = 'llama3.2:1b' }
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
  }
}

# ---- Step 6 : health check -------------------------------------------------

Say 'Attente de la sante du coach (timeout 120s)'
if (-not (Wait-Http -Url $HealthUrl -Name 'Coach /__coach/health' -TimeoutSec 120)) {
  Warn "Le coach n'a pas repondu a temps. Verifier les logs : .\pwnzzai.ps1 logs coach"
}

# Mode cohorte : verification best-effort du dashboard prof.
if ($Mode -eq 'cohorte' -and $dashboardUrl) {
  $reachable = $false
  try { Invoke-WebRequest -Uri $dashboardUrl -TimeoutSec 3 -UseBasicParsing *> $null; $reachable = $true } catch { }
  if ($reachable) {
    Ok "Dashboard prof joignable depuis l'hote : $dashboardUrl"
  } else {
    Warn "Dashboard prof $dashboardUrl injoignable depuis l'hote (best-effort)."
    Warn "Note : le coach vise cette URL DEPUIS le conteneur ; verifier que le prof a"
    Warn 'deploye le dashboard, que le LAN est plat, et le firewall.'
  }
}

# ---- Step 7 : recap --------------------------------------------------------

$lanIp = Get-LanIp

Write-Host ''
Write-Host '========================================================================'
Write-Host "Installation OK (mode $Mode)" -ForegroundColor Green
Write-Host ''
Write-Host "  La stack PwnzzAI complete tourne sur cette machine (le coach EST le lab)."
Write-Host ''
Write-Host "  Eleve  -> $CoachUrl        (entrypoint coach : labs + indices + juge)"
Write-Host "  Brut   -> $RawUrl        (PwnzzAI OWASP brut, sans coach)"
Write-Host "  Sante  -> $HealthUrl   (attendu: ""ollama"": true)"
Write-Host ''
Write-Host "  Cohorte           : $cohortVal"
Write-Host "  Instance (label)  : $labelVal"
if ($Mode -eq 'cohorte') {
  Write-Host "  Dashboard prof    : $dashboardUrl   (events pousses depuis le coach)"
} else {
  Write-Host '  Dashboard prof    : (aucun) - mode solo, le coach marche en local.'
  Write-Host '                      Pour rejoindre une cohorte : relancer avec -Dashboard <ip-prof>'
  Write-Host "                      ex : .\scripts\install-student.ps1 -Dashboard $lanIp -Cohort $cohortVal"
}
Write-Host ''
Write-Host '  Stop  : .\pwnzzai.ps1 down        (ou : docker compose down)'
Write-Host '  Wipe  : .\pwnzzai.ps1 wipe        (DESTRUCTIF : docker compose down -v)'
Write-Host '  Logs  : .\pwnzzai.ps1 logs        (ou : docker compose logs -f)'
Write-Host ''
Write-Host '  Idempotent : relancer ce script ne casse rien et preserve les valeurs valides'
Write-Host '  deja presentes dans .env.'
Write-Host '========================================================================'
