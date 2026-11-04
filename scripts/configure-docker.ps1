param(
    [Parameter(Mandatory = $true)][string]$GoldDirectory,
    [switch]$PresentationAccounts,
    [string]$GeminiEnvFile
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repoRoot '.env'
if (Test-Path -LiteralPath $envPath) {
    throw 'O .env já existe e foi preservado. Edite-o para mudar configurações; não regenere senhas de um volume existente.'
}
$goldPath = (Resolve-Path -LiteralPath $GoldDirectory).Path.Replace('\', '/')
$manifestPath = Join-Path $goldPath 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Informe a pasta que contém manifest.json Gold v2.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.schema_version -ne 'gold-csv-v2') { throw 'O pacote precisa usar schema_version=gold-csv-v2.' }
if ($goldPath -match '[\r\n"$]') { throw 'O caminho contém caracteres incompatíveis com o arquivo de ambiente.' }

function New-LocalSecret {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) } finally { $generator.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}

$geminiKey = ''
if ($GeminiEnvFile) {
    foreach ($line in Get-Content -LiteralPath $GeminiEnvFile) {
        if ($line -match '^\s*GENAI_GEMINI_API_KEY\s*=\s*(.*?)\s*$') {
            $geminiKey = $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    if ($geminiKey -match '[\r\n"$]') { throw 'Formato da chave incompatível com .env.' }
}
$presentation = 'false'
$presentationPassword = ''
if ($PresentationAccounts) { $presentation = 'true'; $presentationPassword = 'senha123' }
$lines = @(
    'COMPOSE_PROJECT_NAME=git-or-treat',
    ('GOLD_CSV_V2_HOST_DIR="' + $goldPath + '"'),
    ('DOCKER_DATABASE_PASSWORD=' + (New-LocalSecret)),
    ('DOCKER_APP_PASSWORD=' + (New-LocalSecret)),
    ('DOCKER_READER_PASSWORD=' + (New-LocalSecret)),
    ('DOCKER_CADASTRO_PASSWORD=' + (New-LocalSecret)),
    ('DOCKER_SERVICE_TOKEN=' + (New-LocalSecret)),
    ('DOCKER_AUDIT_TOKEN=' + (New-LocalSecret)),
    ('LOCAL_PRESENTATION_ACCOUNTS=' + $presentation),
    ('LOCAL_PRESENTATION_PASSWORD=' + $presentationPassword),
    'GENAI_MODEL_PROVIDER=gemini',
    'GENAI_GEMINI_MODEL=gemini-3.5-flash-lite',
    ('GENAI_GEMINI_API_KEY=' + $geminiKey),
    'GENAI_GOLD_APPROVED_CONTROLS=[]'
)
[IO.File]::WriteAllLines($envPath, $lines, (New-Object Text.UTF8Encoding $false))
Write-Host '.env local criado sem imprimir segredos. Configure a chave e somente controles já aprovados; depois execute docker compose up --build -d.'
