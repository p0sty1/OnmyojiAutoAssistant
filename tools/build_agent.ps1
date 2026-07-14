[CmdletBinding()]
param(
    [string]$ProjectRoot = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$root = [IO.Path]::GetFullPath($ProjectRoot)
$python = Join-Path $root '.venv\Scripts\python.exe'
$entry = Join-Path $root 'agent\main.py'
$output = Join-Path $root 'agent\runtime'
$work = Join-Path $root 'build\pyinstaller'
$dist = Join-Path $root 'build\agent-dist'
$spec = Join-Path $root 'build'

if (-not (Test-Path -LiteralPath $python)) {
    throw 'Missing .venv. Run: python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt'
}
if (-not (Test-Path -LiteralPath $entry)) {
    throw "Missing Agent entry: $entry"
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name onmyoji_auto_assistant_agent `
    --distpath $dist `
    --workpath $work `
    --specpath $spec `
    --collect-all maa `
    $entry
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

if (Test-Path -LiteralPath $output) {
    $resolvedOutput = [IO.Path]::GetFullPath($output)
    if (-not $resolvedOutput.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace Agent runtime outside project root: $resolvedOutput"
    }
    Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
}

Copy-Item -LiteralPath (Join-Path $dist 'onmyoji_auto_assistant_agent') -Destination $output -Recurse
$exe = Join-Path $output 'onmyoji_auto_assistant_agent.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Agent executable was not produced: $exe"
}
& $python (Join-Path $PSScriptRoot 'smoke_agent.py') $exe
if ($LASTEXITCODE -ne 0) {
    throw "Agent handshake smoke test failed with exit code $LASTEXITCODE"
}
Write-Host "Built Agent runtime: $exe"
