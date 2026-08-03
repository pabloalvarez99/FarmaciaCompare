#Requires -Version 5.1
<#
.SYNOPSIS
  One-shot local bootstrap: Docker stack, schema, scraper venv, smoke checks.

.DESCRIPTION
  Professional local setup for FarmaciaCompare:
  1. Ensure Docker engine is up
  2. Start postgres + redis
  3. Align env files to compose ports
  4. pnpm install + prisma db push
  5. poetry install for workers/scraper
  6. pytest (offline)
  7. Optional: sync-pharmacies

.PARAMETER WithElasticsearch
  Also start Elasticsearch (heavier; not required for scrapers).

.PARAMETER SyncPharmacies
  Insert online pharmacy rows for all registered chains.

.PARAMETER SkipTests
  Skip scraper unit tests.

.EXAMPLE
  .\scripts\setup-local.ps1 -SyncPharmacies
#>
[CmdletBinding()]
param(
  [switch]$WithElasticsearch,
  [switch]$SyncPharmacies,
  [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'dev-env.ps1')

function Wait-DockerEngine {
  param([int]$TimeoutSec = 180)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    & docker info 1>$null 2>$null
    if ($LASTEXITCODE -eq 0) { return }
    Start-Sleep -Seconds 3
  }
  throw "Docker engine not ready after ${TimeoutSec}s. Open Docker Desktop and re-run."
}

function Wait-ContainerHealthy {
  param([string]$Name, [int]$TimeoutSec = 120)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    $status = & docker inspect --format='{{.State.Health.Status}}' $Name 2>$null
    if ($status -eq 'healthy') { return }
    if (-not $status) {
      $running = & docker inspect --format='{{.State.Running}}' $Name 2>$null
      if ($running -eq 'true') { return }
    }
    Start-Sleep -Seconds 2
  }
  throw "Container $Name not healthy after ${TimeoutSec}s"
}

Write-Host "==> 1/7 Docker engine" -ForegroundColor Cyan
$dockerDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
if (-not (Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue)) {
  if (Test-Path $dockerDesktop) {
    Start-Process $dockerDesktop
    Write-Host "    launched Docker Desktop"
  }
}
Wait-DockerEngine
Write-Host "    engine OK: $(docker version --format '{{.Server.Version}}')"

Write-Host "==> 2/7 Compose: postgres + redis" -ForegroundColor Cyan
$services = @('postgres', 'redis')
if ($WithElasticsearch) { $services += 'elasticsearch' }
fc-compose up -d @services
Wait-ContainerHealthy -Name 'farmacia_postgres'
Write-Host "    postgres healthy on :5432"

Write-Host "==> 3/7 Env alignment (5432)" -ForegroundColor Cyan
$rootEnv = Join-Path $RepoRoot '.env'
if (Test-Path $rootEnv) {
  $content = Get-Content $rootEnv -Raw
  $fixed = $content -replace 'localhost:5433', 'localhost:5432'
  if ($fixed -ne $content) {
    Set-Content -Path $rootEnv -Value $fixed -NoNewline
    Write-Host "    fixed root .env port 5433 -> 5432"
  }
}
$scraperEnv = Join-Path $RepoRoot 'workers\scraper\.env'
if (-not (Test-Path $scraperEnv)) {
  @"
DATABASE_URL=postgresql+asyncpg://farmacia:farmacia@localhost:5432/farmaciacompare
"@ | Set-Content -Path $scraperEnv -Encoding utf8
  Write-Host "    wrote workers/scraper/.env"
}

Write-Host "==> 4/7 pnpm install + prisma db push" -ForegroundColor Cyan
Push-Location $RepoRoot
try {
  $env:CI = 'true'
  pnpm install --force
  if ($LASTEXITCODE -ne 0) { throw "pnpm install failed ($LASTEXITCODE)" }
  $env:DATABASE_URL = 'postgresql://farmacia:farmacia@localhost:5432/farmaciacompare'
  pnpm --filter @farmacia/database exec prisma db push --skip-generate
  if ($LASTEXITCODE -ne 0) {
    # generate may need to run first on clean installs
    pnpm --filter @farmacia/database exec prisma generate
    pnpm --filter @farmacia/database exec prisma db push
  }
  if ($LASTEXITCODE -ne 0) { throw "prisma db push failed ($LASTEXITCODE)" }
  Write-Host "    schema applied"
}
finally {
  Pop-Location
}

Write-Host "==> 5/7 poetry install (scraper)" -ForegroundColor Cyan
$scraper = Join-Path $RepoRoot 'workers\scraper'
Push-Location $scraper
try {
  poetry config virtualenvs.in-project true
  poetry env use python
  poetry install --no-interaction
  if ($LASTEXITCODE -ne 0) { throw "poetry install failed ($LASTEXITCODE)" }
}
finally {
  Pop-Location
}

if (-not $SkipTests) {
  Write-Host "==> 6/7 scraper unit tests" -ForegroundColor Cyan
  Push-Location $scraper
  try {
    poetry run pytest -q --ignore=tests/test_dr_simi.py
    if ($LASTEXITCODE -ne 0) { throw "pytest failed ($LASTEXITCODE)" }
  }
  finally {
    Pop-Location
  }
}
else {
  Write-Host "==> 6/7 scraper unit tests SKIPPED" -ForegroundColor Yellow
}

Write-Host "==> 7/7 optional pharmacy seed" -ForegroundColor Cyan
if ($SyncPharmacies) {
  Push-Location $scraper
  try {
    poetry run scraper sync-pharmacies
    if ($LASTEXITCODE -ne 0) { throw "sync-pharmacies failed ($LASTEXITCODE)" }
  }
  finally {
    Pop-Location
  }
}
else {
  Write-Host "    skip (pass -SyncPharmacies to seed online store rows)"
}

Write-Host ""
Write-Host "Local stack ready." -ForegroundColor Green
Write-Host "  Postgres:  localhost:5432  (farmacia/farmacia / farmaciacompare)"
Write-Host "  Redis:     localhost:6379"
Write-Host "  Scraper:   cd workers\scraper; poetry run scraper list-chains"
Write-Host "  Dry-run:   poetry run scraper scrape salcobrand --dry-run --limit 5"
Write-Host "  Full run:  poetry run scraper scrape-all   # hits live sites — be gentle"
Write-Host ""
Write-Host "Reload shell PATH:  . .\scripts\dev-env.ps1"
