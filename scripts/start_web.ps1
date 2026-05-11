Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $RootDir "configuration/.env"
$ComposeFile = Join-Path $RootDir "configuration/docker-compose.yml"

if (-not (Test-Path $EnvFile)) {
    throw "Missing $EnvFile. Copy configuration/.env.example to configuration/.env first."
}

docker compose --env-file $EnvFile -f $ComposeFile up --build -d db web

Write-Host "Web interface: http://localhost:8000"
