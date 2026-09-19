[CmdletBinding()]
param(
    [string]$GameRoot = ''
)

$ErrorActionPreference = 'Stop'
if (-not $GameRoot) {
    $GameRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$source = Join-Path $projectRoot 'src\discovery_probe.py'
$catalogSource = Join-Path $projectRoot 'src\planet_object_types.py'
$settingsSource = Join-Path $projectRoot 'src\scanner_settings.py'
$targetDirectory = Join-Path $GameRoot 'GAMEDATA\MODS'
$target = Join-Path $targetDirectory 'discovery_probe.py'
$catalogTarget = Join-Path $targetDirectory 'planet_object_types.py'
$settingsTarget = Join-Path $targetDirectory 'scanner_settings.py'

if (Get-Process -Name NMS -ErrorAction SilentlyContinue) {
    throw 'NMS.exe is running. Close the game normally before deployment.'
}

$environment = & (Join-Path $PSScriptRoot 'check-environment.ps1') -GameRoot $GameRoot
$testedVersion = '178994'
if ($environment.FileVersion -ne $testedVersion) {
    Write-Warning "NMS.exe $($environment.FileVersion) differs from the tested $testedVersion; checking signatures."
}

$requiredHooks = @(
    'SubmitDiscoveryPipelineV70Candidate',
    'IsDiscoveryKnown',
    'PostSubmitDiscovery',
    'UpdateScannableMarkers',
    'NmsPyInternalUpdate',
    'NmsPyInternalFsmStateChange',
    'NmsPyInternalStateChange'
)
foreach ($hookName in $requiredHooks) {
    $result = $environment.Signatures | Where-Object Hook -eq $hookName
    if ($null -eq $result -or $result.MatchCount -ne 1) {
        throw "Hook $hookName must have exactly one match; found $($result.MatchCount). Deployment stopped."
    }
}

if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Mod source was not found: $source"
}
if (-not (Test-Path -LiteralPath $catalogSource -PathType Leaf)) {
    throw "Object type catalogue was not found: $catalogSource"
}
if (-not (Test-Path -LiteralPath $settingsSource -PathType Leaf)) {
    throw "Settings module was not found: $settingsSource"
}
if (Test-Path -LiteralPath $target -PathType Leaf) {
    $marker = Select-String -LiteralPath $target -SimpleMatch 'NMSDiscoveryLab stage-' -Quiet
    if (-not $marker) {
        throw "$target already exists and is not owned by NMSDiscoveryLab. It will not be overwritten."
    }
}
if (Test-Path -LiteralPath $catalogTarget -PathType Leaf) {
    $catalogMarker = Select-String -LiteralPath $catalogTarget -SimpleMatch 'Generated NMS 7.0 scannable object scene hashes' -Quiet
    if (-not $catalogMarker) {
        throw "$catalogTarget already exists and is not owned by NMSDiscoveryLab. It will not be overwritten."
    }
}
if (Test-Path -LiteralPath $settingsTarget -PathType Leaf) {
    $settingsMarker = Select-String -LiteralPath $settingsTarget `
        -SimpleMatch 'Persistent user settings for Planetary Discovery Scanner' -Quiet
    if (-not $settingsMarker) {
        throw "$settingsTarget already exists and is not owned by NMSDiscoveryLab. It will not be overwritten."
    }
}

New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
Copy-Item -LiteralPath $source -Destination $target -Force
Copy-Item -LiteralPath $catalogSource -Destination $catalogTarget -Force
Copy-Item -LiteralPath $settingsSource -Destination $settingsTarget -Force

$hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
$catalogHash = (Get-FileHash -LiteralPath $catalogTarget -Algorithm SHA256).Hash
$settingsHash = (Get-FileHash -LiteralPath $settingsTarget -Algorithm SHA256).Hash
Write-Host "Deployed mod: $target"
Write-Host "SHA256 probe: $hash"
Write-Host "Deployed catalogue: $catalogTarget"
Write-Host "SHA256 catalog: $catalogHash"
Write-Host "Deployed settings module: $settingsTarget"
Write-Host "SHA256 settings module: $settingsHash"
Write-Host "To disable the mod, run UNINSTALL.cmd or remove these two files."
