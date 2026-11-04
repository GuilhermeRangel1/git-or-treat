param(
    [ValidateRange(1024, 65535)][int]$BackendPort = 8001,
    [ValidateRange(1024, 65535)][int]$FrontendPort = 5173,
    [string]$DatabaseUrl,
    [string]$DatabaseContainer
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot 'backend'
$frontendRoot = Join-Path $repoRoot 'frontend'
$pythonCandidates = @(
    (Join-Path $backendRoot '.venv/Scripts/python.exe'),
    (Join-Path $backendRoot 'venv/Scripts/python.exe')
)
$pythonPath = $null
foreach ($candidate in $pythonCandidates) {
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $previousErrorActionPreference = $ErrorActionPreference
    $pythonProbeExitCode = 1
    try {
        # Test the backend's runtime dependency without exposing import errors or installing packages.
        $ErrorActionPreference = 'Continue'
        $pythonProbe = & $candidate -c 'import pwdlib' 2>&1
        $pythonProbeExitCode = $LASTEXITCODE
    } catch {
        $pythonProbeExitCode = 1
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Variable pythonProbe -ErrorAction SilentlyContinue
    }
    if ($pythonProbeExitCode -eq 0) { $pythonPath = $candidate; break }
}
$bootstrapPath = Join-Path $backendRoot 'scripts/bootstrap_local_auth.py'
$vitePath = Join-Path $frontendRoot 'node_modules/vite/bin/vite.js'
$runRoot = Join-Path $repoRoot 'work/dev131-local-auth'
$processFile = Join-Path $runRoot 'processes.json'
$apiUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://127.0.0.1:$FrontendPort"

if ($BackendPort -eq $FrontendPort) { throw 'Use portas diferentes para API e frontend.' }
if ([string]::IsNullOrWhiteSpace($pythonPath)) { throw 'Ambiente Python ausente ou sem pwdlib. Prepare um venv com as dependências de backend/requirements.txt.' }
if (-not (Test-Path -LiteralPath $bootstrapPath)) { throw 'Bootstrap de autenticação ausente em backend/scripts/bootstrap_local_auth.py.' }
if (-not (Test-Path -LiteralPath $vitePath)) { throw 'Dependências do frontend ausentes. Execute npm.cmd ci em frontend.' }
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source

function Test-GoldLocalPort([int]$Port) {
    $client = New-Object Net.Sockets.TcpClient
    try { $pending = $client.ConnectAsync('127.0.0.1', $Port); return $pending.Wait(500) -and $client.Connected }
    catch { return $false }
    finally { $client.Dispose() }
}

function Read-DatabaseUrlFromBackendEnv([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*DATABASE_URL\s*=\s*(.*)\s*$') {
            $value = $Matches[1].Trim()
            if ($value.Length -ge 2 -and (($value[0] -eq '"' -and $value[$value.Length - 1] -eq '"') -or ($value[0] -eq "'" -and $value[$value.Length - 1] -eq "'"))) {
                return $value.Substring(1, $value.Length - 2)
            }
            return $value
        }
    }
    return $null
}

function Get-DatabaseUrlFromContainer([string]$Name) {
    $dockerPath = (Get-Command docker.exe -ErrorAction Stop).Source
    $inspectJson = $null
    $container = $null
    $containerEnv = @{}
    $dbPassword = $null
    try {
        $inspectJson = & $dockerPath inspect --type=container $Name 2>$null
        if ($LASTEXITCODE -ne 0) { throw 'Não foi possível inspecionar o container PostgreSQL informado.' }
        try { $container = @(ConvertFrom-Json -InputObject ($inspectJson -join "`n"))[0] }
        catch { throw 'A inspeção do container PostgreSQL não retornou dados válidos.' }

        if ($container.State.Running -ne $true) { throw 'O container PostgreSQL informado não está em execução; o launcher não inicia containers.' }
        if ($container.Config.Image -notmatch '^postgres(?::|@)') { throw 'O container informado não usa a imagem oficial postgres.' }

        $bindings = @($container.NetworkSettings.Ports.'5432/tcp' | Where-Object { $null -ne $_ })
        $nonLocalBindings = @($bindings | Where-Object { $_.HostIp -ne '127.0.0.1' })
        if ($bindings.Count -eq 0 -or $nonLocalBindings.Count -gt 0) {
            throw 'A porta PostgreSQL do container deve estar publicada exclusivamente em 127.0.0.1.'
        }
        if ($bindings.Count -ne 1 -or $bindings[0].HostPort -notmatch '^\d+$') {
            throw 'Esperava exatamente um binding local para a porta PostgreSQL do container.'
        }
        $databasePort = [int]$bindings[0].HostPort
        if (-not (Test-GoldLocalPort $databasePort)) { throw 'A porta PostgreSQL local do container não está acessível.' }

        foreach ($entry in $container.Config.Env) {
            $pair = $entry -split '=', 2
            if ($pair.Count -eq 2 -and $pair[0] -in @('POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD')) {
                $containerEnv[$pair[0]] = $pair[1]
            }
        }
        foreach ($key in @('POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD')) {
            if ([string]::IsNullOrWhiteSpace($containerEnv[$key])) { throw "O container PostgreSQL não tem $key definido." }
        }

        $dbName = [Uri]::EscapeDataString($containerEnv['POSTGRES_DB'])
        $dbUser = [Uri]::EscapeDataString($containerEnv['POSTGRES_USER'])
        $dbPassword = [Uri]::EscapeDataString($containerEnv['POSTGRES_PASSWORD'])
        return "postgresql+psycopg://${dbUser}:${dbPassword}@127.0.0.1:${databasePort}/${dbName}"
    } finally {
        $containerEnv.Clear()
        Remove-Variable inspectJson, container, dbPassword, dbName, dbUser, bindings, nonLocalBindings, databasePort -ErrorAction SilentlyContinue
    }
}

function Test-ConfiguredServiceTokens([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^\s*(ORDERS_READ_TOKEN|ORDERS_WRITE_TOKEN)\s*=\s*(.*)$') {
            $value = $Matches[2].Trim()
            if ($value.Length -ge 2 -and (($value[0] -eq '"' -and $value[$value.Length - 1] -eq '"') -or ($value[0] -eq "'" -and $value[$value.Length - 1] -eq "'"))) {
                $value = $value.Substring(1, $value.Length - 2).Trim()
            }
            if (-not [string]::IsNullOrWhiteSpace($value)) { return $true }
        }
    }
    return $false
}

function Test-HttpStatus([string]$Url, [int]$ExpectedStatus) {
    try { $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2; return $response.StatusCode -eq $ExpectedStatus }
    catch { if ($null -ne $_.Exception.Response) { return [int]$_.Exception.Response.StatusCode -eq $ExpectedStatus }; return $false }
}

if ((Test-GoldLocalPort $BackendPort) -or (Test-GoldLocalPort $FrontendPort)) {
    throw "Uma porta já está em uso ($BackendPort/$FrontendPort). Nenhum processo foi encerrado; escolha outras portas ou encerre manualmente a instância existente."
}

$resolvedDatabaseUrl = $null
if (-not [string]::IsNullOrWhiteSpace($DatabaseContainer)) {
    if (-not [string]::IsNullOrWhiteSpace($DatabaseUrl)) { throw 'Use -DatabaseContainer ou -DatabaseUrl, não os dois.' }
    $resolvedDatabaseUrl = Get-DatabaseUrlFromContainer $DatabaseContainer
} else {
    $resolvedDatabaseUrl = $DatabaseUrl
    if ([string]::IsNullOrWhiteSpace($resolvedDatabaseUrl)) { $resolvedDatabaseUrl = [Environment]::GetEnvironmentVariable('DATABASE_URL', 'Process') }
    if ([string]::IsNullOrWhiteSpace($resolvedDatabaseUrl)) { $resolvedDatabaseUrl = Read-DatabaseUrlFromBackendEnv (Join-Path $backendRoot '.env') }
}
if ([string]::IsNullOrWhiteSpace($resolvedDatabaseUrl)) { throw 'DATABASE_URL ausente. Configure backend/.env, informe -DatabaseUrl ou selecione -DatabaseContainer.' }

$backendEnvPath = Join-Path $backendRoot '.env'
if (Test-ConfiguredServiceTokens $backendEnvPath) { throw 'Remova ORDERS_READ_TOKEN/ORDERS_WRITE_TOKEN não vazios de backend/.env para usar autenticação individual por sessão.' }

New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
$runId = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$environmentNames = @('APP_ENV', 'ANALYTICS_SOURCE', 'ORDERS_AUTH_MODE', 'DATABASE_URL', 'ORDERS_READ_TOKEN', 'ORDERS_WRITE_TOKEN', 'BACKEND_CORS_ORIGINS', 'VITE_API_URL', 'API_PROXY_TARGET')
$previousEnvironment = @{}
foreach ($name in $environmentNames) { $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
$apiProcess = $null
$frontendProcess = $null
$previousLocation = Get-Location
try {
    $env:APP_ENV = 'development'
    $env:ANALYTICS_SOURCE = 'gold'
    $env:ORDERS_AUTH_MODE = 'session'
    $env:DATABASE_URL = $resolvedDatabaseUrl
    $env:ORDERS_READ_TOKEN = $null
    $env:ORDERS_WRITE_TOKEN = $null
    $env:BACKEND_CORS_ORIGINS = "[`"http://localhost:$FrontendPort`",`"http://127.0.0.1:$FrontendPort`"]"
    $env:VITE_API_URL = '/'
    $env:API_PROXY_TARGET = $apiUrl

    # Migrations are deliberately explicit and must be applied by the operator before this launcher.
    Set-Location -LiteralPath $backendRoot
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5 promotes native stderr records to terminating errors under Stop.
        # Capture INFO/WARNING output privately and rely on the native exit code for the check.
        $ErrorActionPreference = 'Continue'
        $migrationCheck = & $pythonPath -m alembic current --check-heads 2>&1
        $migrationExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Variable migrationCheck -ErrorAction SilentlyContinue
    }
    if ($migrationExitCode -ne 0) { throw 'O banco não está na revisão Alembic atual. Aplique as migrações explicitamente e tente novamente; o launcher não migra.' }
    & $pythonPath $bootstrapPath 1>$null
    if ($LASTEXITCODE -ne 0) { throw 'A provisão de usuários falhou. Confira migrações e conexão do banco; nenhuma migração foi aplicada pelo launcher.' }

    $apiProcess = Start-Process -FilePath $pythonPath -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$BackendPort", '--no-access-log') `
        -RedirectStandardOutput (Join-Path $runRoot "$runId-api.log") -RedirectStandardError (Join-Path $runRoot "$runId-api-error.log")
    $frontendProcess = Start-Process -FilePath $nodePath -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru `
        -ArgumentList @(('"{0}"' -f $vitePath), '--host', '127.0.0.1', '--port', "$FrontendPort", '--strictPort') `
        -RedirectStandardOutput (Join-Path $runRoot "$runId-frontend.log") -RedirectStandardError (Join-Path $runRoot "$runId-frontend-error.log")

    $timer = [Diagnostics.Stopwatch]::StartNew()
    $ready = $false
    while ($timer.Elapsed.TotalSeconds -lt 60) {
        if ($apiProcess.HasExited -or $frontendProcess.HasExited) { throw "Um serviço encerrou durante a inicialização. Consulte os logs em $runRoot." }
        $ready = (Test-HttpStatus "$apiUrl/api/v1/auth/session" 200) -and (Test-HttpStatus "$frontendUrl/" 200)
        if ($ready) { break }
        Start-Sleep -Milliseconds 300
    }
    if (-not $ready) { throw "Gold com sessão local não ficou pronta em 60 segundos. Consulte os logs em $runRoot." }

    [pscustomobject]@{ api_pid = $apiProcess.Id; frontend_pid = $frontendProcess.Id; api_url = $apiUrl; frontend_url = $frontendUrl } |
        ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding UTF8
    Write-Host "Portal Gold local pronto: $frontendUrl"
    Write-Host "API local: $apiUrl. Credenciais de provisão: work/local-auth/credentials.txt"
    Write-Host "API PID $($apiProcess.Id); frontend PID $($frontendProcess.Id). Logs: $runRoot"
} catch {
    if ($frontendProcess -and -not $frontendProcess.HasExited) { $frontendProcess.Kill() }
    if ($apiProcess -and -not $apiProcess.HasExited) { $apiProcess.Kill() }
    throw
} finally {
    Set-Location -LiteralPath $previousLocation
    foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process') }
    Remove-Variable resolvedDatabaseUrl -ErrorAction SilentlyContinue
}
