param(
    [ValidateRange(1024, 65535)][int]$BackendPort = 8000,
    [ValidateRange(1024, 65535)][int]$FrontendPort = 5173
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
$demoRoot = Join-Path $repoRoot 'work/dev06-demo'
$databasePath = Join-Path $demoRoot 'orders.sqlite'
$processFile = Join-Path $demoRoot "processes-$BackendPort-$FrontendPort.json"
$apiUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://127.0.0.1:$FrontendPort"
$pageUrl = "http://localhost:$FrontendPort/ordens"

if ($BackendPort -eq $FrontendPort) { throw 'Use portas diferentes para API e frontend.' }
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Ambiente Python ausente. Prepare backend/.venv conforme backend/README.md.'
}
if (-not (Test-Path -LiteralPath $vitePath)) {
    throw 'Dependencias do frontend ausentes. Execute npm.cmd ci em frontend.'
}
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source

function Test-DemoPort([int]$Port) {
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

if ((Test-DemoPort $BackendPort) -or (Test-DemoPort $FrontendPort)) {
    if (Test-Path -LiteralPath $processFile) {
        try {
            $previousRun = Get-Content -Raw -LiteralPath $processFile | ConvertFrom-Json
            if ($previousRun.database_path -eq $databasePath) {
                $access = Invoke-RestMethod "$apiUrl/api/v1/inspections/access" -TimeoutSec 2
                $orders = Invoke-RestMethod "$frontendUrl/api/v1/inspections/orders/search" -TimeoutSec 2
                if ($access.auth_mode -eq 'demo' -and $null -ne $orders.pagination) {
                    Write-Host "Demo de ordens ja esta ativa: $pageUrl"
                    Write-Host "Banco persistente: $databasePath"
                    return
                }
            }
        } catch { }
    }
    throw "Uma porta ja esta em uso ($BackendPort/$FrontendPort). Nenhum processo foi encerrado. Use -BackendPort 8010 -FrontendPort 5180 ou confira a instancia existente."
}

New-Item -ItemType Directory -Force -Path $demoRoot | Out-Null
$runId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$environmentNames = @('APP_ENV', 'ANALYTICS_SOURCE', 'ORDERS_AUTH_MODE', 'DATABASE_URL', 'BACKEND_CORS_ORIGINS', 'VITE_API_URL', 'API_PROXY_TARGET')
$previousEnvironment = @{}
foreach ($name in $environmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$apiProcess = $null
$frontendProcess = $null
$previousLocation = Get-Location
try {
    $env:APP_ENV = 'development'
    $env:ANALYTICS_SOURCE = 'synthetic'
    $env:ORDERS_AUTH_MODE = 'demo'
    $env:DATABASE_URL = 'sqlite:///' + $databasePath.Replace('\', '/')
    $env:BACKEND_CORS_ORIGINS = "[`"http://localhost:$FrontendPort`",`"http://127.0.0.1:$FrontendPort`"]"
    $env:VITE_API_URL = '/'
    $env:API_PROXY_TARGET = $apiUrl

    Set-Location -LiteralPath $backendRoot
    & $pythonPath -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel aplicar as migracoes no banco local da demo.' }

    $apiProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort") `
        -RedirectStandardOutput (Join-Path $demoRoot "$runId-api.log") -RedirectStandardError (Join-Path $demoRoot "$runId-api-error.log")
    $frontendProcess = Start-Process -FilePath $nodePath -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru `
        -ArgumentList @(('"{0}"' -f $vitePath), '--host', '127.0.0.1', '--port', "$FrontendPort", '--strictPort') `
        -RedirectStandardOutput (Join-Path $demoRoot "$runId-frontend.log") -RedirectStandardError (Join-Path $demoRoot "$runId-frontend-error.log")

    $timer = [Diagnostics.Stopwatch]::StartNew()
    $ready = $false
    while ($timer.Elapsed.TotalSeconds -lt 30) {
        if ($apiProcess.HasExited -or $frontendProcess.HasExited) {
            throw "Um servico encerrou durante a inicializacao. Consulte os logs em $demoRoot."
        }
        try {
            $access = Invoke-RestMethod "$apiUrl/api/v1/inspections/access" -TimeoutSec 2
            $orders = Invoke-RestMethod "$frontendUrl/api/v1/inspections/orders/search" -TimeoutSec 2
            $page = Invoke-WebRequest "$frontendUrl/ordens" -UseBasicParsing -TimeoutSec 2
            $ready = $access.auth_mode -eq 'demo' -and $null -ne $orders.pagination -and $page.StatusCode -eq 200
        } catch { $ready = $false }
        if ($ready) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw "A demo nao ficou pronta em 30 segundos. Consulte os logs em $demoRoot." }

    [pscustomobject]@{
        api_pid = $apiProcess.Id
        frontend_pid = $frontendProcess.Id
        api_url = $apiUrl
        page_url = $pageUrl
        database_path = $databasePath
    } | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding UTF8
    Write-Host "Demo de ordens pronta: $pageUrl"
    Write-Host 'Sem login. Se a lista estiver vazia, crie uma ordem pela pagina Inspecoes.'
    Write-Host "Banco persistente: $databasePath"
    Write-Host "API PID $($apiProcess.Id); frontend PID $($frontendProcess.Id). Logs: $demoRoot"
} catch {
    # Encerra apenas os processos criados por esta chamada; preserva o banco.
    if ($frontendProcess -and -not $frontendProcess.HasExited) { $frontendProcess.Kill() }
    if ($apiProcess -and -not $apiProcess.HasExited) { $apiProcess.Kill() }
    throw
} finally {
    Set-Location -LiteralPath $previousLocation
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
