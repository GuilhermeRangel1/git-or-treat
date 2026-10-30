param(
    [ValidateRange(1024, 65535)][int]$BackendPort = 8001,
    [ValidateRange(1024, 65535)][int]$FrontendPort = 5173,
    [string]$DatabaseUrl
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot 'backend'
$frontendRoot = Join-Path $repoRoot 'frontend'
$pythonPath = Join-Path $backendRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = Join-Path $backendRoot 'venv/Scripts/python.exe'
}
$vitePath = Join-Path $frontendRoot 'node_modules/vite/bin/vite.js'
$runRoot = Join-Path $repoRoot 'work/dev131-oidc'
$processFile = Join-Path $runRoot 'processes.json'
$apiUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://127.0.0.1:$FrontendPort"
$issuer = 'http://localhost:8082/realms/grid360'
$discoveryUrl = "$issuer/.well-known/openid-configuration"
$providerLauncher = Join-Path $backendRoot 'scripts/start_local_oidc.py'

if ($BackendPort -eq $FrontendPort) { throw 'Use portas diferentes para API e frontend.' }
if ($FrontendPort -ne 5173) {
    throw 'O provedor local esta configurado para o callback do frontend em localhost:5173; use a porta padrao.'
}
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Ambiente Python ausente. Prepare backend/.venv conforme backend/README.md.'
}
if (-not (Test-Path -LiteralPath $vitePath)) {
    throw 'Dependencias do frontend ausentes. Execute npm.cmd ci em frontend.'
}
if (-not (Test-Path -LiteralPath $providerLauncher)) {
    throw 'Launcher do provedor OIDC ausente em backend/scripts/start_local_oidc.py.'
}
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source

function Test-GoldOidcPort([int]$Port) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $pending = $client.ConnectAsync('127.0.0.1', $Port)
        return $pending.Wait(500) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Read-DatabaseUrlFromBackendEnv([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*DATABASE_URL\s*=\s*(.*)\s*$') {
            $value = $Matches[1].Trim()
            if ($value.Length -ge 2 -and (($value[0] -eq '"' -and $value[$value.Length - 1] -eq '"') -or ($value[0] -eq "'" -and $value[$value.Length - 1] -eq "'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }
    return $null
}

function Test-HttpStatus([string]$Url, [int]$ExpectedStatus) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq $ExpectedStatus
    } catch {
        if ($null -ne $_.Exception.Response) {
            return [int]$_.Exception.Response.StatusCode -eq $ExpectedStatus
        }
        return $false
    }
}

function Test-AnonymousApiUnauthorized([string]$Url) {
    # An unauthenticated 401 proves the API is reachable and OIDC protection is active.
    try {
        $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $false
    } catch {
        if ($null -ne $_.Exception.Response) {
            return [int]$_.Exception.Response.StatusCode -eq 401
        }
        return $false
    }
}

if ((Test-GoldOidcPort $BackendPort) -or (Test-GoldOidcPort $FrontendPort)) {
    throw "Uma porta ja esta em uso ($BackendPort/$FrontendPort). Nenhum processo foi encerrado. Escolha outras portas ou encerre manualmente a instancia existente."
}

$resolvedDatabaseUrl = $DatabaseUrl
if ([string]::IsNullOrWhiteSpace($resolvedDatabaseUrl)) {
    $resolvedDatabaseUrl = [Environment]::GetEnvironmentVariable('DATABASE_URL', 'Process')
}
if ([string]::IsNullOrWhiteSpace($resolvedDatabaseUrl)) {
    $resolvedDatabaseUrl = Read-DatabaseUrlFromBackendEnv (Join-Path $backendRoot '.env')
}
if ([string]::IsNullOrWhiteSpace($resolvedDatabaseUrl)) {
    throw 'DATABASE_URL ausente. Configure backend/.env ou informe -DatabaseUrl com uma conexao existente.'
}

$backendEnvPath = Join-Path $backendRoot '.env'
if (Test-Path -LiteralPath $backendEnvPath) {
    $configuredOrderTokenNames = Get-Content -LiteralPath $backendEnvPath |
        Where-Object { $_ -match '^\s*(ORDERS_READ_TOKEN|ORDERS_WRITE_TOKEN)\s*=' } |
        ForEach-Object { ([regex]::Match($_, '^\s*(ORDERS_READ_TOKEN|ORDERS_WRITE_TOKEN)')).Groups[1].Value } |
        Select-Object -Unique
    if ($configuredOrderTokenNames.Count -gt 0) {
        throw 'Remova ORDERS_READ_TOKEN/ORDERS_WRITE_TOKEN de backend/.env antes de iniciar OIDC local; o arquivo e carregado pela API.'
    }
}

New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
$runId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$environmentNames = @(
    'APP_ENV', 'ANALYTICS_SOURCE', 'ORDERS_AUTH_MODE', 'OIDC_ALLOW_LOCAL_HTTP',
    'OIDC_ISSUER', 'OIDC_AUDIENCE', 'OIDC_JWKS_URL', 'DATABASE_URL',
    'ORDERS_READ_TOKEN', 'ORDERS_WRITE_TOKEN',
    'BACKEND_CORS_ORIGINS', 'VITE_API_URL', 'VITE_OIDC_AUTHORITY',
    'VITE_OIDC_CLIENT_ID', 'API_PROXY_TARGET'
)
$previousEnvironment = @{}
foreach ($name in $environmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$apiProcess = $null
$frontendProcess = $null
$previousLocation = Get-Location
try {
    # Start the companion local Keycloak launcher; its output is kept out of the console.
    $providerLog = Join-Path $runRoot "$runId-provider.log"
    $providerErrorLog = Join-Path $runRoot "$runId-provider-error.log"
    Set-Location -LiteralPath $repoRoot
    $providerProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru -Wait `
        -ArgumentList @(('"{0}"' -f $providerLauncher)) `
        -RedirectStandardOutput $providerLog -RedirectStandardError $providerErrorLog
    if ($providerProcess.ExitCode -ne 0) { throw "O provedor OIDC local nao iniciou. Consulte os logs em $runRoot." }

    $providerTimer = [Diagnostics.Stopwatch]::StartNew()
    $providerReady = $false
    while ($providerTimer.Elapsed.TotalSeconds -lt 120) {
        try {
            $discovery = Invoke-RestMethod -Uri $discoveryUrl -TimeoutSec 3
            $providerReady = $discovery.issuer -eq $issuer
        } catch { $providerReady = $false }
        if ($providerReady) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $providerReady) { throw 'O provedor OIDC nao publicou o issuer esperado em 120 segundos.' }

    $env:APP_ENV = 'development'
    $env:ANALYTICS_SOURCE = 'gold'
    $env:ORDERS_AUTH_MODE = 'oidc'
    $env:OIDC_ALLOW_LOCAL_HTTP = 'true'
    $env:OIDC_ISSUER = $issuer
    $env:OIDC_AUDIENCE = 'grid360-api'
    $env:OIDC_JWKS_URL = "$issuer/protocol/openid-connect/certs"
    $env:DATABASE_URL = $resolvedDatabaseUrl
    $env:ORDERS_READ_TOKEN = $null
    $env:ORDERS_WRITE_TOKEN = $null
    $env:BACKEND_CORS_ORIGINS = "[`"http://localhost:$FrontendPort`",`"http://127.0.0.1:$FrontendPort`"]"
    $env:VITE_API_URL = '/'
    $env:VITE_OIDC_AUTHORITY = $issuer
    $env:VITE_OIDC_CLIENT_ID = 'grid360-web'
    $env:API_PROXY_TARGET = $apiUrl

    $apiProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort", '--no-access-log') `
        -RedirectStandardOutput (Join-Path $runRoot "$runId-api.log") -RedirectStandardError (Join-Path $runRoot "$runId-api-error.log")
    $frontendProcess = Start-Process -FilePath $nodePath -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru `
        -ArgumentList @(('"{0}"' -f $vitePath), '--host', '127.0.0.1', '--port', "$FrontendPort", '--strictPort') `
        -RedirectStandardOutput (Join-Path $runRoot "$runId-frontend.log") -RedirectStandardError (Join-Path $runRoot "$runId-frontend-error.log")

    $timer = [Diagnostics.Stopwatch]::StartNew()
    $ready = $false
    while ($timer.Elapsed.TotalSeconds -lt 60) {
        if ($apiProcess.HasExited -or $frontendProcess.HasExited) {
            throw "Um servico encerrou durante a inicializacao. Consulte os logs em $runRoot."
        }
        $providerReady = $false
        try {
            $discovery = Invoke-RestMethod -Uri $discoveryUrl -TimeoutSec 2
            $providerReady = $discovery.issuer -eq $issuer
        } catch { }
        $ready = $providerReady -and
            (Test-AnonymousApiUnauthorized "$apiUrl/api/v1/inspections/access") -and
            (Test-HttpStatus "$frontendUrl/" 200)
        if ($ready) { break }
        Start-Sleep -Milliseconds 300
    }
    if (-not $ready) { throw "Gold/OIDC nao ficou pronta em 60 segundos. Consulte os logs em $runRoot." }

    [pscustomobject]@{
        api_pid = $apiProcess.Id
        frontend_pid = $frontendProcess.Id
        api_url = $apiUrl
        frontend_url = $frontendUrl
        issuer = $issuer
    } | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding UTF8
    Write-Host "Portal Gold/OIDC pronto: http://localhost:$FrontendPort"
    Write-Host "API local: $apiUrl; provedor: $issuer"
    Write-Host "API PID $($apiProcess.Id); frontend PID $($frontendProcess.Id). Logs: $runRoot"
} catch {
    # Encerra apenas os processos filhos iniciados por esta chamada.
    if ($frontendProcess -and -not $frontendProcess.HasExited) { $frontendProcess.Kill() }
    if ($apiProcess -and -not $apiProcess.HasExited) { $apiProcess.Kill() }
    throw
} finally {
    Set-Location -LiteralPath $previousLocation
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
