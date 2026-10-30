# Read-only local inventory. Does not start InDesign, install packages, or edit MCP config.
[CmdletBinding()]
param([string]$RuntimePath)

$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$taskWindows = $env:OS -eq 'Windows_NT'
$taskCandidates = @(
    (Join-Path $taskRoot '.local/runtime/nutria-mcp'),
    (Join-Path $taskRoot 'tools/nutria-mcp')
)
if ($RuntimePath) {
    if (-not [IO.Path]::IsPathRooted($RuntimePath)) {
        $RuntimePath = Join-Path (Get-Location).Path $RuntimePath
    }
    $taskRuntime = [IO.Path]::GetFullPath($RuntimePath)
} else {
    $taskRuntime = $taskCandidates[0]
    foreach ($taskCandidate in $taskCandidates) {
        if (Test-Path -LiteralPath (Join-Path $taskCandidate 'package.json') -PathType Leaf) {
            $taskRuntime = $taskCandidate
            break
        }
    }
}

$taskNode = Get-Command node -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$taskGit = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
$taskNpmName = if ($taskWindows) { 'npm.cmd' } else { 'npm' }
$taskNpm = Get-Command $taskNpmName -ErrorAction SilentlyContinue | Select-Object -First 1
$taskNodeVersion = $null
$taskNodeReady = $false
if ($taskNode) {
    $taskNodeOutput = @(& $taskNode.Source --version 2>$null)
    $taskNodeVersion = $taskNodeOutput | Select-Object -First 1
    if ($taskNodeVersion -match '^v(\d+)\.') {
        $taskNodeReady = [int]$Matches[1] -ge 18
    }
}

$taskPackagePath = Join-Path $taskRuntime 'package.json'
$taskPackage = $null
$taskPackageError = $null
if (Test-Path -LiteralPath $taskPackagePath -PathType Leaf) {
    try { $taskPackage = Get-Content -LiteralPath $taskPackagePath -Raw | ConvertFrom-Json }
    catch { $taskPackageError = 'Invalid package.json' }
}
$taskPackageMatches = $null -ne $taskPackage -and $taskPackage.name -eq 'indesign-nutria-mcp'
$taskBuilt = Test-Path -LiteralPath (Join-Path $taskRuntime 'dist/index.js') -PathType Leaf
$taskDependencies = Test-Path -LiteralPath (Join-Path $taskRuntime 'node_modules/@modelcontextprotocol/sdk/package.json') -PathType Leaf
$taskStatus = 'installed-unverified'
if (-not $taskNodeReady) { $taskStatus = 'missing-or-unsupported-node' }
elseif ($null -eq $taskPackage -and $null -eq $taskPackageError) { $taskStatus = 'missing-runtime' }
elseif (-not $taskPackageMatches) { $taskStatus = 'unexpected-or-invalid-package' }
elseif (-not $taskDependencies) { $taskStatus = 'missing-dependencies' }
elseif (-not $taskBuilt) { $taskStatus = 'needs-build' }

$taskComRegistered = $false
if ($taskWindows) {
    $taskComRegistered = Test-Path -LiteralPath 'Registry::HKEY_CLASSES_ROOT\InDesign.Application' -ErrorAction SilentlyContinue
}
$taskRunning = @(Get-Process -Name InDesign -ErrorAction SilentlyContinue).Count -gt 0
$taskReport = [ordered]@{
    status = $taskStatus
    runtimePath = $taskRuntime
    windows = $taskWindows
    node = $taskNodeVersion
    gitAvailable = $null -ne $taskGit
    npmAvailable = $null -ne $taskNpm
    packageVersion = $(if ($taskPackageMatches) { $taskPackage.version } else { $null })
    packageError = $taskPackageError
    builtEntryExists = $taskBuilt
    dependenciesPresent = $taskDependencies
    albumExtensionSourcePresent = (Test-Path -LiteralPath (Join-Path $taskRuntime 'src/handlers/AlbumHandler.ts') -PathType Leaf)
    indesignProcessRunning = $taskRunning
    genericComRegistrationFound = $taskComRegistered
    clientToolDiscovery = 'not-checked-by-this-script'
    liveBridgeHealth = 'not-probed; call a read-only MCP tool from the client'
    note = 'COM registration may vary by version. Local files do not prove the MCP client or InDesign connection works.'
    instructions = 'docs/indesign-mcp-setup.md'
}
$taskReport | ConvertTo-Json -Depth 5
if ($taskStatus -eq 'installed-unverified') { exit 0 }
exit 2
