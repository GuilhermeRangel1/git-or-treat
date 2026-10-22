param(
    [ValidateRange(1024, 65535)][int]$BackendPort = 8000,
    [ValidateRange(1024, 65535)][int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot 'backend'
$frontendRoot = Join-Path $repoRoot 'frontend'
$pythonPath = Join-Path $backendRoot 'venv/Scripts/python.exe'
$vitePath = Join-Path $frontendRoot 'node_modules/vite/bin/vite.js'
$apiUrl = "http://localhost:$BackendPort"
$pageUrl = "http://localhost:$FrontendPort/inspecoes"

if ($BackendPort -eq $FrontendPort) { throw 'Use portas diferentes para API e frontend.' }
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Ambiente backend/venv ausente. Prepare o backend conforme backend/README.md.'
}
if (-not (Test-Path -LiteralPath $vitePath)) {
    throw 'Dependências do frontend ausentes. Execute npm.cmd ci em frontend.'
}
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
$occupied = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalPort -in @($BackendPort, $FrontendPort) }
if ($occupied) {
    try {
        $existingQueue = Invoke-RestMethod "$apiUrl/api/v1/inspections/queue?page_size=1" -TimeoutSec 2
        $existingClient = Invoke-WebRequest "http://localhost:$FrontendPort/src/shared/api/client.ts" -UseBasicParsing -TimeoutSec 2
        if ($existingQueue.metadata.source.is_demo -eq $true -and $null -ne $existingQueue.data.summary -and $existingClient.Content.Contains($apiUrl)) {
            Write-Host "Demo sintética já está ativa: $pageUrl"
            return
        }
    } catch { }
    throw "Uma porta da demo já está em uso ($BackendPort/$FrontendPort). Nenhum processo foi encerrado. Confira a demo em $pageUrl ou escolha outras portas."
}

$logRoot = Join-Path $repoRoot 'work/dev05-demo'
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$runId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$environmentNames = @('ANALYTICS_SOURCE', 'DATABASE_URL', 'BACKEND_CORS_ORIGINS', 'VITE_API_URL')
$previousEnvironment = @{}
foreach ($name in $environmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$apiProcess = $null
$frontendProcess = $null
try {
    $env:ANALYTICS_SOURCE = 'synthetic'
    $env:DATABASE_URL = 'sqlite:///:memory:'
    $env:BACKEND_CORS_ORIGINS = "[`"http://localhost:$FrontendPort`",`"http://127.0.0.1:$FrontendPort`"]"
    $env:VITE_API_URL = $apiUrl
    $apiProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort") `
        -RedirectStandardOutput (Join-Path $logRoot "$runId-api.log") -RedirectStandardError (Join-Path $logRoot "$runId-api-error.log")
    $frontendProcess = Start-Process -FilePath $nodePath -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru `
        -ArgumentList @(('"{0}"' -f $vitePath), '--host', '127.0.0.1', '--port', "$FrontendPort", '--strictPort') `
        -RedirectStandardOutput (Join-Path $logRoot "$runId-frontend.log") -RedirectStandardError (Join-Path $logRoot "$runId-frontend-error.log")

    $timer = [Diagnostics.Stopwatch]::StartNew()
    $ready = $false
    while ($timer.Elapsed.TotalSeconds -lt 30) {
        if ($apiProcess.HasExited -or $frontendProcess.HasExited) {
            throw "Um serviço encerrou durante a inicialização. Consulte os logs em $logRoot."
        }
        try {
            $queue = Invoke-RestMethod "$apiUrl/api/v1/inspections/queue?page_size=1" -TimeoutSec 2
            $front = Invoke-WebRequest $pageUrl -UseBasicParsing -TimeoutSec 2
            $ready = $queue.metadata.source.is_demo -eq $true -and $null -ne $queue.data.summary -and $front.StatusCode -eq 200
        } catch { $ready = $false }
        if ($ready) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw "A demo não ficou pronta em 30 segundos. Consulte os logs em $logRoot." }

    [pscustomobject]@{
        api_pid = $apiProcess.Id
        frontend_pid = $frontendProcess.Id
        api_url = $apiUrl
        page_url = $pageUrl
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $logRoot "processes-$BackendPort-$FrontendPort.json") -Encoding UTF8
    Write-Host "Demo sintética pronta: $pageUrl"
    Write-Host "API PID $($apiProcess.Id); frontend PID $($frontendProcess.Id). Logs: $logRoot"
    Write-Host 'Processos em segundo plano. Nenhum arquivo .env foi alterado; ordens não têm persistência nesta demo.'
} catch {
    # Stop only processes created by this invocation, never an existing listener.
    if ($frontendProcess -and -not $frontendProcess.HasExited) { $frontendProcess.Kill() }
    if ($apiProcess -and -not $apiProcess.HasExited) { $apiProcess.Kill() }
    throw
} finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
