[CmdletBinding()]
param(
    [string]$Version = '0.1.0',
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath($ProjectRoot)
$releaseRoot = Join-Path $root 'release'
$packageName = "YYS520Helper-win-x64-v$Version"
$packageRoot = Join-Path $releaseRoot $packageName
$zipPath = Join-Path $releaseRoot "$packageName.zip"

function Assert-ProjectChild {
    param([Parameter(Mandatory)] [string]$Path)
    $resolved = [IO.Path]::GetFullPath($Path)
    if (-not $resolved.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify path outside project root: $resolved"
    }
}

$runtimeRequired = @(
    (Join-Path $root 'mxu.exe'),
    (Join-Path $root 'maafw\MaaFramework.dll'),
    (Join-Path $root 'maafw\MaaToolkit.dll'),
    (Join-Path $root 'maafw\MaaAgentBinary')
)
if (@($runtimeRequired | Where-Object { -not (Test-Path -LiteralPath $_) }).Count -gt 0) {
    & (Join-Path $PSScriptRoot 'install_runtime.ps1') -DestinationRoot $root
}

if (-not $SkipTests) {
    $validator = Join-Path $PSScriptRoot 'validate_project.ps1'
    if (Test-Path -LiteralPath $validator) {
        & $validator
    }

    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Missing .venv required for tests and packaging.'
    }
    & $python -m pytest (Join-Path $root 'tests') -q
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed with exit code $LASTEXITCODE"
    }
}

& (Join-Path $PSScriptRoot 'build_agent.ps1') -ProjectRoot $root

New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
foreach ($oldPath in @($packageRoot, $zipPath)) {
    if (Test-Path -LiteralPath $oldPath) {
        Assert-ProjectChild -Path $oldPath
        Remove-Item -LiteralPath $oldPath -Recurse -Force
    }
}
New-Item -ItemType Directory -Path $packageRoot | Out-Null

$files = @(
    'interface.json',
    'README.md',
    'THIRD_PARTY_NOTICES.md',
    'Start YYS Helper.cmd',
    'mxu.exe'
)
foreach ($relative in $files) {
    $source = Join-Path $root $relative
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Missing release file: $source"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $packageRoot $relative) -Force
}

foreach ($relative in @('resource_pack', 'tasks', 'docs', 'maafw', 'third_party')) {
    $source = Join-Path $root $relative
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $packageRoot $relative) -Recurse -Force
    }
}

$agentTarget = Join-Path $packageRoot 'agent'
New-Item -ItemType Directory -Force -Path $agentTarget | Out-Null
Copy-Item -Path (Join-Path $root 'agent\*.py') -Destination $agentTarget -Force
Copy-Item -LiteralPath (Join-Path $root 'agent\runtime') -Destination (Join-Path $agentTarget 'runtime') -Recurse -Force

foreach ($generatedPath in @(
    (Join-Path $packageRoot 'maafw\config'),
    (Join-Path $packageRoot 'maafw\debug'),
    (Join-Path $packageRoot 'agent\runtime\debug')
)) {
    if (Test-Path -LiteralPath $generatedPath) {
        Assert-ProjectChild -Path $generatedPath
        Remove-Item -LiteralPath $generatedPath -Recurse -Force
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot 'tools') | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'start.ps1') -Destination (Join-Path $packageRoot 'tools\start.ps1') -Force

$interfacePath = Join-Path $packageRoot 'interface.json'
$interface = Get-Content -LiteralPath $interfacePath -Raw -Encoding UTF8 | ConvertFrom-Json
$interface.version = $Version
[IO.File]::WriteAllText(
    $interfacePath,
    ($interface | ConvertTo-Json -Depth 100),
    [Text.UTF8Encoding]::new($false)
)

Compress-Archive -LiteralPath $packageRoot -DestinationPath $zipPath -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "Release: $zipPath"
Write-Host "SHA-256: $hash"
