[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [switch]$RequireRuntime
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Add-Failure {
    param([string]$Message)
    $script:failures.Add($Message)
}

function Add-Warning {
    param([string]$Message)
    $script:warnings.Add($Message)
}

function Test-Property {
    param($Object, [string]$Name)
    return $null -ne $Object -and $null -ne $Object.PSObject.Properties[$Name]
}

function Read-JsonFile {
    param([string]$Path)

    try {
        return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        Add-Failure "Cannot parse JSON: $Path ($($_.Exception.Message))"
        return $null
    }
}

function Resolve-ProjectPath {
    param([string]$RelativePath, [string]$Context)

    $candidate = [System.IO.Path]::GetFullPath((Join-Path $script:rootFull $RelativePath))
    $rootPrefix = $script:rootFull.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    if (-not $candidate.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        Add-Failure "$Context escapes the project root: $RelativePath"
        return $null
    }
    return $candidate
}

$rootFull = [System.IO.Path]::GetFullPath($ProjectRoot)
$interfacePath = Join-Path $rootFull "interface.json"
if (-not (Test-Path -LiteralPath $interfacePath -PathType Leaf)) {
    Add-Failure "Missing interface.json: $interfacePath"
}

$interface = if (Test-Path -LiteralPath $interfacePath -PathType Leaf) {
    Read-JsonFile $interfacePath
}
else {
    $null
}

if ($null -eq $interface) {
    foreach ($failure in $failures) { Write-Host "[FAIL] $failure" -ForegroundColor Red }
    exit 1
}

foreach ($required in @("interface_version", "name", "controller", "resource")) {
    if (-not (Test-Property $interface $required)) {
        Add-Failure "interface.json is missing required field: $required"
    }
}

if ((Test-Property $interface "interface_version") -and $interface.interface_version -ne 2) {
    Add-Failure "interface_version must be the number 2"
}

$controllerNames = @{}
foreach ($controller in @($interface.controller)) {
    if (-not (Test-Property $controller "name") -or [string]::IsNullOrWhiteSpace([string]$controller.name)) {
        Add-Failure "controller has an empty name"
        continue
    }
    if ($controllerNames.ContainsKey($controller.name)) {
        Add-Failure "Duplicate controller name: $($controller.name)"
    }
    $controllerNames[$controller.name] = $controller
}

if (-not $controllerNames.ContainsKey("Android")) {
    Add-Failure "Missing Android controller"
}
else {
    $android = $controllerNames["Android"]
    if ($android.type -ne "Adb") { Add-Failure "Android controller.type must be Adb" }
    if (-not (Test-Property $android "display_short_side") -or $android.display_short_side -ne 720) {
        Add-Failure "Android controller.display_short_side must be 720"
    }
    if (Test-Property $android "display_long_side") { Add-Failure "display_short_side and display_long_side are mutually exclusive" }
    if ((Test-Property $android "display_raw") -and $android.display_raw) { Add-Failure "display_raw cannot be enabled with normalized 720p resources" }
}

$resourceNames = @{}
$resourcePaths = @()
foreach ($resource in @($interface.resource)) {
    if (-not (Test-Property $resource "name") -or [string]::IsNullOrWhiteSpace([string]$resource.name)) {
        Add-Failure "resource has an empty name"
        continue
    }
    if ($resourceNames.ContainsKey($resource.name)) { Add-Failure "Duplicate resource name: $($resource.name)" }
    $resourceNames[$resource.name] = $resource

    foreach ($path in @($resource.path)) {
        $resolved = Resolve-ProjectPath ([string]$path) "resource.path"
        if ($null -eq $resolved) { continue }
        if (-not (Test-Path -LiteralPath $resolved -PathType Container)) {
            Add-Failure "resource.path does not exist: $path"
        }
        else {
            $resourcePaths += $resolved
        }
    }
}

$tasks = @()
$options = @{}
if (Test-Property $interface "task") { $tasks += @($interface.task) }
if (Test-Property $interface "option") {
    foreach ($property in $interface.option.PSObject.Properties) { $options[$property.Name] = $property.Value }
}

foreach ($importPath in @($interface.import)) {
    $resolved = Resolve-ProjectPath ([string]$importPath) "import"
    if ($null -eq $resolved) { continue }
    if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
        Add-Failure "Import file does not exist: $importPath"
        continue
    }

    $fragment = Read-JsonFile $resolved
    if ($null -eq $fragment) { continue }
    foreach ($property in $fragment.PSObject.Properties) {
        if ($property.Name -notin @("task", "option", "preset")) {
            Add-Failure "Import fragment uses an unsupported base MXU field: $importPath#$($property.Name)"
        }
    }
    if (Test-Property $fragment "task") { $tasks += @($fragment.task) }
    if (Test-Property $fragment "option") {
        foreach ($property in $fragment.option.PSObject.Properties) {
            if ($options.ContainsKey($property.Name)) { Add-Failure "Duplicate option definition: $($property.Name)" }
            $options[$property.Name] = $property.Value
        }
    }
}

$taskNames = @{}
foreach ($task in $tasks) {
    if (-not (Test-Property $task "name") -or [string]::IsNullOrWhiteSpace([string]$task.name)) {
        Add-Failure "task has an empty name"
        continue
    }
    if ($taskNames.ContainsKey($task.name)) { Add-Failure "Duplicate task name: $($task.name)" }
    $taskNames[$task.name] = $task
    if (-not (Test-Property $task "entry") -or [string]::IsNullOrWhiteSpace([string]$task.entry)) {
        Add-Failure "task is missing entry: $($task.name)"
    }
    if (Test-Property $task "controller") {
        foreach ($controllerName in @($task.controller)) {
            if (-not $controllerNames.ContainsKey([string]$controllerName)) {
                Add-Failure "task references an unknown controller: $($task.name) -> $controllerName"
            }
        }
    }
    if (Test-Property $task "resource") {
        foreach ($resourceName in @($task.resource)) {
            if (-not $resourceNames.ContainsKey([string]$resourceName)) {
                Add-Failure "task references an unknown resource: $($task.name) -> $resourceName"
            }
        }
    }
    if (Test-Property $task "option") {
        foreach ($optionName in @($task.option)) {
            if (-not $options.ContainsKey([string]$optionName)) {
                Add-Failure "task references an unknown option: $($task.name) -> $optionName"
            }
        }
    }
}

foreach ($expectedTask in @("yys_tower", "yys_realm_raid")) {
    if (-not $taskNames.ContainsKey($expectedTask)) { Add-Failure "Missing expected task: $expectedTask" }
}

foreach ($optionName in $options.Keys) {
    $definition = $options[$optionName]
    $type = if (Test-Property $definition "type") { [string]$definition.type } else { "select" }
    if ($type -notin @("select", "switch", "checkbox", "input", "hotkey")) {
        Add-Failure "Unsupported option.type: $optionName -> $type"
        continue
    }
    if ($type -in @("select", "switch", "checkbox")) {
        if (-not (Test-Property $definition "cases") -or @($definition.cases).Count -eq 0) {
            Add-Failure "option is missing cases: $optionName"
            continue
        }
        $caseNames = @{}
        foreach ($case in @($definition.cases)) {
            if (-not (Test-Property $case "name")) { Add-Failure "option case is missing name: $optionName"; continue }
            if ($caseNames.ContainsKey($case.name)) { Add-Failure "Duplicate option case: $optionName -> $($case.name)" }
            $caseNames[$case.name] = $true
        }
        if (Test-Property $definition "default_case") {
            foreach ($defaultCase in @($definition.default_case)) {
                if (-not $caseNames.ContainsKey([string]$defaultCase)) {
                    Add-Failure "option.default_case is not defined: $optionName -> $defaultCase"
                }
            }
        }
    }
}

$pipelineNodes = @{}
foreach ($resourcePath in $resourcePaths) {
    $pipelinePath = Join-Path $resourcePath "pipeline"
    if (-not (Test-Path -LiteralPath $pipelinePath -PathType Container)) {
        Add-Failure "Resource package is missing pipeline directory: $pipelinePath"
        continue
    }
    foreach ($file in Get-ChildItem -LiteralPath $pipelinePath -Recurse -File -Filter "*.json") {
        $pipeline = Read-JsonFile $file.FullName
        if ($null -eq $pipeline) { continue }
        foreach ($property in $pipeline.PSObject.Properties) {
            if ($pipelineNodes.ContainsKey($property.Name)) {
                Add-Failure "Duplicate Pipeline node: $($property.Name) ($($pipelineNodes[$property.Name]) / $($file.FullName))"
            }
            else {
                $pipelineNodes[$property.Name] = $file.FullName
            }
        }
    }
}

foreach ($task in $tasks) {
    if ((Test-Property $task "entry") -and -not $pipelineNodes.ContainsKey([string]$task.entry)) {
        Add-Failure "task.entry does not exist in Pipeline: $($task.name) -> $($task.entry)"
    }
    if (Test-Property $task "pipeline_override") {
        foreach ($property in $task.pipeline_override.PSObject.Properties) {
            if (-not $pipelineNodes.ContainsKey($property.Name)) {
                Add-Failure "task pipeline_override references an unknown node: $($task.name) -> $($property.Name)"
            }
        }
    }
}

foreach ($optionName in $options.Keys) {
    $definition = $options[$optionName]
    if (-not (Test-Property $definition "cases")) { continue }
    foreach ($case in @($definition.cases)) {
        if (-not (Test-Property $case "pipeline_override")) { continue }
        foreach ($property in $case.pipeline_override.PSObject.Properties) {
            if (-not $pipelineNodes.ContainsKey($property.Name)) {
                Add-Failure "option pipeline_override references an unknown node: $optionName/$($case.name) -> $($property.Name)"
            }
        }
    }
}

if (Test-Property $interface "agent") {
    foreach ($agent in @($interface.agent)) {
        if (-not (Test-Property $agent "child_exec")) {
            Add-Failure "agent is missing child_exec"
            continue
        }
        $childExec = [string]$agent.child_exec
        if ($childExec.StartsWith(".")) {
            $resolved = Resolve-ProjectPath $childExec "agent.child_exec"
            if ($null -ne $resolved -and -not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
                if ($RequireRuntime) { Add-Failure "Agent runtime does not exist: $childExec" }
                else { Add-Warning "Agent runtime has not been built yet: $childExec" }
            }
        }
    }
}

if ($RequireRuntime) {
    foreach ($runtimePath in @("./mxu.exe", "./maafw/MaaFramework.dll", "./maafw/MaaToolkit.dll")) {
        $resolved = Resolve-ProjectPath $runtimePath "runtime"
        if ($null -ne $resolved -and -not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
            Add-Failure "Required runtime file does not exist: $runtimePath"
        }
    }
}

foreach ($warning in $warnings) { Write-Host "[WARN] $warning" -ForegroundColor Yellow }
if ($failures.Count -gt 0) {
    foreach ($failure in $failures) { Write-Host "[FAIL] $failure" -ForegroundColor Red }
    Write-Host "Validation failed with $($failures.Count) error(s)." -ForegroundColor Red
    exit 1
}

Write-Host "Validation passed: $($tasks.Count) task(s), $($options.Count) option(s), $($pipelineNodes.Count) Pipeline node(s)." -ForegroundColor Green
