[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$required = @(
    (Join-Path $root 'interface.json'),
    (Join-Path $root 'mxu.exe'),
    (Join-Path $root 'maafw\MaaFramework.dll'),
    (Join-Path $root 'maafw\MaaToolkit.dll'),
    (Join-Path $root 'agent\runtime\yys520_agent.exe')
)

$missing = @($required | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    $message = "The application is not ready. Missing:`n" + ($missing -join "`n") + "`n`nRun tools\install_runtime.ps1 and tools\build_agent.ps1 first."
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show($message, 'YYS 520 Helper', 'OK', 'Error') | Out-Null
    exit 1
}

Start-Process -FilePath (Join-Path $root 'mxu.exe') -WorkingDirectory $root
