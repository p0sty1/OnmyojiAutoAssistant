[CmdletBinding()]
param(
    [string]$DestinationRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Versions = @{
    MaaFramework = 'v5.12.1'
    MXU = 'v2.3.0'
}

$Artifacts = @(
    @{
        Name = 'MaaFramework'
        File = 'MAA-win-x86_64-v5.12.1.zip'
        Uri = 'https://github.com/MaaXYZ/MaaFramework/releases/download/v5.12.1/MAA-win-x86_64-v5.12.1.zip'
        Sha256 = '88255ee3c0c67baf2713afdc51b9955f984033d8ee86c1427e5a7ff975be0f1e'
    },
    @{
        Name = 'MXU'
        File = 'MXU-win-x86_64-v2.3.0.zip'
        Uri = 'https://github.com/MistEO/MXU/releases/download/v2.3.0/MXU-win-x86_64-v2.3.0.zip'
        Sha256 = '1d3573f7247dcd1d4e63fed4b3ce92d01ba3945bf779482387697c231542f53a'
    }
)

$ImportSchema = @{
    Name = 'ProjectInterface import schema'
    File = 'interface_import.schema.v5.12.1.json'
    Uri = 'https://raw.githubusercontent.com/MaaXYZ/MaaFramework/v5.12.1/tools/interface_import.schema.json'
    Sha256 = 'b3022bb635c058d1e9e7f88e0c29a05864c966e6612510b5f905db8710be7c9e'
}

function Get-VerifiedArchive {
    param(
        [Parameter(Mandatory)] [hashtable]$Artifact,
        [Parameter(Mandatory)] [string]$CacheDirectory
    )

    $archive = Join-Path $CacheDirectory $Artifact.File
    if (-not (Test-Path -LiteralPath $archive)) {
        Write-Host "Downloading $($Artifact.Name) $($Artifact.File)..."
        Invoke-WebRequest -Uri $Artifact.Uri -OutFile $archive -UseBasicParsing
    }

    $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Artifact.Sha256) {
        if (Test-Path -LiteralPath $archive) {
            Remove-Item -LiteralPath $archive -Force
        }
        throw "$($Artifact.Name) SHA-256 mismatch. Expected $($Artifact.Sha256), got $actual."
    }
    return $archive
}

function Assert-SafeTemporaryPath {
    param([Parameter(Mandatory)] [string]$Path)

    $resolved = [IO.Path]::GetFullPath($Path)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove non-temporary path: $resolved"
    }
}

$root = [IO.Path]::GetFullPath($DestinationRoot)
New-Item -ItemType Directory -Force -Path $root | Out-Null

$cache = Join-Path ([IO.Path]::GetTempPath()) 'yys520helper-runtime-cache'
New-Item -ItemType Directory -Force -Path $cache | Out-Null

$archives = @{}
foreach ($artifact in $Artifacts) {
    $archives[$artifact.Name] = Get-VerifiedArchive -Artifact $artifact -CacheDirectory $cache
}
$importSchemaPath = Get-VerifiedArchive -Artifact $ImportSchema -CacheDirectory $cache

$extractRoot = Join-Path ([IO.Path]::GetTempPath()) ("yys520helper-install-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $extractRoot | Out-Null

try {
    $frameworkExtract = Join-Path $extractRoot 'maafw'
    $mxuExtract = Join-Path $extractRoot 'mxu'
    Expand-Archive -LiteralPath $archives.MaaFramework -DestinationPath $frameworkExtract
    Expand-Archive -LiteralPath $archives.MXU -DestinationPath $mxuExtract

    $maafwTarget = Join-Path $root 'maafw'
    if ($Force -and (Test-Path -LiteralPath $maafwTarget)) {
        $resolvedTarget = [IO.Path]::GetFullPath($maafwTarget)
        if (-not $resolvedTarget.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to replace MaaFramework outside project root: $resolvedTarget"
        }
        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $maafwTarget | Out-Null
    Copy-Item -Path (Join-Path $frameworkExtract 'bin\*') -Destination $maafwTarget -Recurse -Force
    $agentBinaryTarget = Join-Path $maafwTarget 'MaaAgentBinary'
    New-Item -ItemType Directory -Force -Path $agentBinaryTarget | Out-Null
    Copy-Item -Path (Join-Path $frameworkExtract 'share\MaaAgentBinary\*') -Destination $agentBinaryTarget -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $mxuExtract 'mxu.exe') -Destination (Join-Path $root 'mxu.exe') -Force

    $licenses = Join-Path $root 'third_party'
    New-Item -ItemType Directory -Force -Path $licenses | Out-Null
    Copy-Item -LiteralPath (Join-Path $frameworkExtract 'LICENSE.md') -Destination (Join-Path $licenses 'MaaFramework-LICENSE.md') -Force
    Copy-Item -LiteralPath (Join-Path $mxuExtract 'LICENSE') -Destination (Join-Path $licenses 'MXU-LICENSE.txt') -Force
    Copy-Item -LiteralPath (Join-Path $frameworkExtract 'share\MaaAgentBinary\LICENSE') -Destination (Join-Path $licenses 'MaaAgentBinary-LICENSE.txt') -Force

    $schemaTarget = Join-Path $root 'tools\schemas'
    New-Item -ItemType Directory -Force -Path $schemaTarget | Out-Null
    foreach ($schemaName in @('interface.schema.json', 'pipeline.schema.json', 'custom.action.schema.json', 'custom.recognition.schema.json')) {
        Copy-Item -LiteralPath (Join-Path $frameworkExtract "tools\$schemaName") -Destination (Join-Path $schemaTarget $schemaName) -Force
    }
    Copy-Item -LiteralPath $importSchemaPath -Destination (Join-Path $schemaTarget 'interface_import.schema.json') -Force

    Write-Host "Installed MaaFramework $($Versions.MaaFramework) and MXU $($Versions.MXU) to $root"
}
finally {
    if (Test-Path -LiteralPath $extractRoot) {
        Assert-SafeTemporaryPath -Path $extractRoot
        Remove-Item -LiteralPath $extractRoot -Recurse -Force
    }
}
