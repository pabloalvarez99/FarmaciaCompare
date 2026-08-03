#Requires -Version 5.1
<#
.SYNOPSIS
  Load FarmaciaCompare local tooling into the current PowerShell session.

.DESCRIPTION
  Puts Docker CLI, Python user Scripts (poetry/uv), and project helpers on PATH
  for this session. Does not change machine-wide settings.

.EXAMPLE
  . .\scripts\dev-env.ps1
  docker version
  poetry --version
#>
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot 'package.json'))) {
  # scripts/ is under repo root
  $RepoRoot = $PSScriptRoot
  if (-not (Test-Path (Join-Path $RepoRoot 'package.json'))) {
    throw "Cannot resolve FarmaciaCompare root from $PSScriptRoot"
  }
}

$env:FARMACIA_ROOT = $RepoRoot
$env:SECOND_BRAIN = if ($env:SECOND_BRAIN) { $env:SECOND_BRAIN } else { 'D:\obsidian-mind' }

# Canonical local stack ports (must match infra/docker/docker-compose.yml)
$env:DATABASE_URL = if ($env:DATABASE_URL) {
  $env:DATABASE_URL
} else {
  'postgresql://farmacia:farmacia@localhost:5432/farmaciacompare'
}
$env:REDIS_URL = if ($env:REDIS_URL) { $env:REDIS_URL } else { 'redis://localhost:6379' }

$prepend = [System.Collections.Generic.List[string]]::new()

$dockerBin = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'
if (Test-Path (Join-Path $dockerBin 'docker.exe')) {
  $prepend.Add($dockerBin)
}

$pythonUserScripts = Join-Path $env:APPDATA 'Python\Python312\Scripts'
if (Test-Path $pythonUserScripts) { $prepend.Add($pythonUserScripts) }

$pythonLocalScripts = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\Scripts'
if (Test-Path $pythonLocalScripts) { $prepend.Add($pythonLocalScripts) }

$scraperVenvScripts = Join-Path $RepoRoot 'workers\scraper\.venv\Scripts'
if (Test-Path $scraperVenvScripts) { $prepend.Add($scraperVenvScripts) }

$current = $env:PATH -split ';' | Where-Object { $_ }
foreach ($p in $prepend) {
  if ($current -notcontains $p) {
    $env:PATH = "$p;$env:PATH"
  }
}

function Invoke-FarmaciaCompose {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
  )
  $composeFile = Join-Path $env:FARMACIA_ROOT 'infra\docker\docker-compose.yml'
  & docker compose -f $composeFile @ComposeArgs
}

Set-Alias -Name fc-compose -Value Invoke-FarmaciaCompose -Scope Global -Force -ErrorAction SilentlyContinue

function _cmdSource([string]$Name) {
  $c = Get-Command $Name -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  return '(not found)'
}

Write-Host "FarmaciaCompare env loaded: $env:FARMACIA_ROOT" -ForegroundColor Green
Write-Host "  DATABASE_URL=$env:DATABASE_URL"
Write-Host "  docker:  $(_cmdSource docker)"
Write-Host "  poetry:  $(_cmdSource poetry)"
Write-Host "  uv:      $(_cmdSource uv)"
Write-Host "  helper:  fc-compose <args>  (e.g. fc-compose ps)"
