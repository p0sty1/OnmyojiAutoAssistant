[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Show-UpdateMessage {
    param(
        [Parameter(Mandatory)] [string]$Message,
        [Parameter(Mandatory)] [string]$Title,
        [string]$Buttons = 'OK',
        [string]$Icon = 'Information'
    )

    Add-Type -AssemblyName PresentationFramework
    return [System.Windows.MessageBox]::Show(
        $Message,
        $Title,
        [System.Windows.MessageBoxButton]::$Buttons,
        [System.Windows.MessageBoxImage]::$Icon)
}

function Get-ComparableVersion {
    param([Parameter(Mandatory)] [string]$Version)

    $normalized = $Version.Trim().TrimStart('v')
    try {
        return [Version]$normalized
    }
    catch {
        throw "Unsupported release version: $Version"
    }
}

function Invoke-GitHubJson {
    param([Parameter(Mandatory)] [string]$Uri)

    return Invoke-RestMethod -Uri $Uri -Headers @{ 'User-Agent' = 'OnmyojiAutoAssistant-Updater' } -UseBasicParsing
}

function Get-PackageRoot {
    param([Parameter(Mandatory)] [string]$StagingDirectory)

    if (Test-Path -LiteralPath (Join-Path $StagingDirectory 'interface.json')) {
        return $StagingDirectory
    }

    $candidates = @(Get-ChildItem -LiteralPath $StagingDirectory -Directory | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName 'interface.json')
    })
    if ($candidates.Count -ne 1) {
        throw 'The update archive does not contain exactly one application directory.'
    }
    return $candidates[0].FullName
}

function Test-UpdateArchive {
    param([Parameter(Mandatory)] [string]$ArchivePath)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        foreach ($entry in $archive.Entries) {
            $name = $entry.FullName.Replace('/', '\')
            if ([IO.Path]::IsPathRooted($name) -or $name -match '(^|\\)\.\.(\\|$)') {
                throw "Unsafe path in update archive: $($entry.FullName)"
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Restore-InterruptedUpdate {
    param(
        [Parameter(Mandatory)] [string]$Root,
        [Parameter(Mandatory)] [string]$UpdatesRoot
    )

    $statePath = Join-Path $UpdatesRoot 'pending-update.json'
    if (-not (Test-Path -LiteralPath $statePath)) {
        return
    }

    $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($name in @($state.names)) {
        $current = Join-Path $Root $name
        if (Test-Path -LiteralPath $current) {
            Remove-Item -LiteralPath $current -Recurse -Force
        }

        $backup = Join-Path $state.backup $name
        if (Test-Path -LiteralPath $backup) {
            Move-Item -LiteralPath $backup -Destination $current -Force
        }
    }

    foreach ($relative in @($state.preservedPaths)) {
        $source = Join-Path $state.preserve $relative
        if (Test-Path -LiteralPath $source) {
            $destination = Join-Path $Root $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            Move-Item -LiteralPath $source -Destination $destination -Force
        }
    }

    Remove-Item -LiteralPath $statePath -Force
}

function Install-UpdatePackage {
    param(
        [Parameter(Mandatory)] [string]$Root,
        [Parameter(Mandatory)] [string]$ArchivePath,
        [Parameter(Mandatory)] [string]$UpdatesRoot
    )

    $operationId = [Guid]::NewGuid().ToString('N')
    $staging = Join-Path $UpdatesRoot "staging-$operationId"
    $backup = Join-Path $UpdatesRoot "backup-$operationId"
    $preserve = Join-Path $UpdatesRoot "preserve-$operationId"
    $statePath = Join-Path $UpdatesRoot 'pending-update.json'
    $preservedPaths = @('maafw\debug', 'agent\runtime\debug')

    New-Item -ItemType Directory -Force -Path $staging, $backup, $preserve | Out-Null
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $staging -Force
    $packageRoot = Get-PackageRoot -StagingDirectory $staging
    $names = @(Get-ChildItem -LiteralPath $packageRoot -Force | Where-Object {
        $_.Name -notin @('config', 'debug', 'cache', '.updates')
    } | ForEach-Object Name)
    if ($names.Count -eq 0) {
        throw 'The update archive contains no installable application files.'
    }

    foreach ($relative in $preservedPaths) {
        $source = Join-Path $Root $relative
        if (Test-Path -LiteralPath $source) {
            $destination = Join-Path $preserve $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            Move-Item -LiteralPath $source -Destination $destination -Force
        }
    }

    [ordered]@{
        backup = $backup
        preserve = $preserve
        names = $names
        preservedPaths = $preservedPaths
    } | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8

    try {
        foreach ($name in $names) {
            $destination = Join-Path $Root $name
            if (Test-Path -LiteralPath $destination) {
                Move-Item -LiteralPath $destination -Destination (Join-Path $backup $name) -Force
            }
            Copy-Item -LiteralPath (Join-Path $packageRoot $name) -Destination $destination -Recurse -Force
        }

        foreach ($relative in $preservedPaths) {
            $source = Join-Path $preserve $relative
            if (Test-Path -LiteralPath $source) {
                $destination = Join-Path $Root $relative
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
                Move-Item -LiteralPath $source -Destination $destination -Force
            }
        }

        Remove-Item -LiteralPath $statePath -Force
    }
    catch {
        Restore-InterruptedUpdate -Root $Root -UpdatesRoot $UpdatesRoot
        throw
    }
    finally {
        if (Test-Path -LiteralPath $staging) {
            Remove-Item -LiteralPath $staging -Recurse -Force
        }
    }
}

try {
    $root = [IO.Path]::GetFullPath($ProjectRoot)
    $updatesRoot = Join-Path $root '.updates'
    New-Item -ItemType Directory -Force -Path $updatesRoot | Out-Null
    Restore-InterruptedUpdate -Root $root -UpdatesRoot $updatesRoot

    $settingsPath = Join-Path $root 'update-settings.json'
    if (-not (Test-Path -LiteralPath $settingsPath)) {
        return
    }
    $settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $settings.checkOnStartup -or [string]::IsNullOrWhiteSpace($settings.repository)) {
        return
    }

    $localInterface = Get-Content -LiteralPath (Join-Path $root 'interface.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $release = Invoke-GitHubJson -Uri "https://api.github.com/repos/$($settings.repository)/releases/latest"
    if ($release.draft -or $release.prerelease) {
        return
    }

    $remoteVersion = Get-ComparableVersion -Version $release.tag_name
    if ($remoteVersion -le (Get-ComparableVersion -Version $localInterface.version)) {
        return
    }

    $answer = Show-UpdateMessage -Message "发现新版本 $($release.tag_name)。是否现在下载并安装？" -Title 'Onmyoji Auto Assistant 更新' -Buttons YesNo -Icon Question
    if ($answer -ne [System.Windows.MessageBoxResult]::Yes) {
        return
    }

    $manifestAsset = @($release.assets | Where-Object { $_.name -eq 'update.json' } | Select-Object -First 1)
    if ($manifestAsset.Count -ne 1) {
        throw 'The release is missing update.json.'
    }
    $manifestPath = Join-Path $updatesRoot 'update.json'
    Invoke-WebRequest -Uri $manifestAsset[0].browser_download_url -OutFile $manifestPath -UseBasicParsing
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.version -ne $remoteVersion.ToString() -or [string]::IsNullOrWhiteSpace($manifest.package) -or [string]::IsNullOrWhiteSpace($manifest.sha256)) {
        throw 'The release update manifest is invalid.'
    }

    $packageAsset = @($release.assets | Where-Object { $_.name -eq $manifest.package } | Select-Object -First 1)
    if ($packageAsset.Count -ne 1) {
        throw "The release is missing $($manifest.package)."
    }
    $downloads = Join-Path $updatesRoot 'downloads'
    New-Item -ItemType Directory -Force -Path $downloads | Out-Null
    $archivePath = Join-Path $downloads $manifest.package
    Invoke-WebRequest -Uri $packageAsset[0].browser_download_url -OutFile $archivePath -UseBasicParsing
    $actualHash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $manifest.sha256.ToLowerInvariant()) {
        Remove-Item -LiteralPath $archivePath -Force
        throw 'The downloaded update failed SHA-256 verification.'
    }

    Test-UpdateArchive -ArchivePath $archivePath
    Install-UpdatePackage -Root $root -ArchivePath $archivePath -UpdatesRoot $updatesRoot
    Show-UpdateMessage -Message "已安装 $($release.tag_name)，现在将启动新版本。" -Title 'Onmyoji Auto Assistant 更新' | Out-Null
}
catch {
    try {
        Show-UpdateMessage -Message "自动更新未完成，将继续启动当前版本。`n`n$($_.Exception.Message)" -Title 'Onmyoji Auto Assistant 更新' -Icon Warning | Out-Null
    }
    catch {
        Write-Warning "Automatic update failed: $($_.Exception.Message)"
    }
}
