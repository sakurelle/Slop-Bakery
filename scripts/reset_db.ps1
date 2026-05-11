Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $RootDir "configuration/.env"
$ComposeFile = Join-Path $RootDir "configuration/docker-compose.yml"

if (-not (Test-Path $EnvFile)) {
    throw "Missing $EnvFile. Copy configuration/.env.example to configuration/.env first."
}

$envData = @{}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$') {
        $parts = $_ -split '=', 2
        if ($parts.Count -eq 2) {
            $envData[$parts[0].Trim()] = $parts[1].Trim()
        }
    }
}

$dbName = $envData["POSTGRES_DB"]
$dbUser = $envData["POSTGRES_USER"]

docker compose --env-file $EnvFile -f $ComposeFile up -d db

$dbReady = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
    docker compose --env-file $EnvFile -f $ComposeFile exec -T db `
        pg_isready -U $dbUser -d $dbName | Out-Null

    if ($LASTEXITCODE -eq 0) {
        $dbReady = $true
        break
    }

    Start-Sleep -Seconds 2
}

if (-not $dbReady) {
    throw "PostgreSQL did not become ready in time."
}

docker compose --env-file $EnvFile -f $ComposeFile exec -T db `
    sh -lc "cd /workspace/database/initialization && psql -v ON_ERROR_STOP=1 -U $dbUser -d $dbName -f 99_run_all.sql"
