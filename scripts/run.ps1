[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [switch]$BackupConfirmed,
    [switch]$PreflightOnly,
    [string]$GameRoot = ''
)

$ErrorActionPreference = 'Stop'
if (-not $GameRoot) {
    $GameRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$pymhf = Join-Path $projectRoot '.venv\Scripts\pymhf.exe'
$source = Join-Path $projectRoot 'src\discovery_probe.py'
$catalogSource = Join-Path $projectRoot 'src\planet_object_types.py'
$deployed = Join-Path $GameRoot 'GAMEDATA\MODS\discovery_probe.py'
$catalogDeployed = Join-Path $GameRoot 'GAMEDATA\MODS\planet_object_types.py'
$pymhfConfig = Join-Path $env:APPDATA 'pymhf\nmspy\pymhf.local.toml'

if (-not $BackupConfirmed) {
    throw 'A separate save backup must be confirmed before launching the mod.'
}
if (Get-Process -Name NMS -ErrorAction SilentlyContinue) {
    throw 'NMS.exe is already running. Close it first; pyMHF must launch the game.'
}
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf) -or -not (Test-Path -LiteralPath $pymhf -PathType Leaf)) {
    throw 'The environment is not ready. Run scripts\setup.ps1 with Python 3.13 x64 first.'
}
if (-not (Test-Path -LiteralPath $deployed -PathType Leaf) -or
    -not (Test-Path -LiteralPath $catalogDeployed -PathType Leaf)) {
    throw 'The mod is not deployed. Run scripts\deploy.ps1 first.'
}
if (-not (Test-Path -LiteralPath $pymhfConfig -PathType Leaf)) {
    throw "pyMHF configuration was not found at $pymhfConfig. Run scripts\setup.ps1 again."
}
$configText = Get-Content -LiteralPath $pymhfConfig -Raw -Encoding UTF8
$expectedLogDir = Join-Path $projectRoot 'logs'
$escapedLogDir = $expectedLogDir.Replace('\', '\\')
if (-not $configText.Contains("log_dir = `"$escapedLogDir`"") -or
    $configText -notmatch '(?m)^\s*shown\s*=\s*false\s*$') {
    throw "pyMHF is not configured to write directly to $expectedLogDir. Run scripts\setup.ps1 again."
}
$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$deployedHash = (Get-FileHash -LiteralPath $deployed -Algorithm SHA256).Hash
$catalogSourceHash = (Get-FileHash -LiteralPath $catalogSource -Algorithm SHA256).Hash
$catalogDeployedHash = (Get-FileHash -LiteralPath $catalogDeployed -Algorithm SHA256).Hash
if ($sourceHash -ne $deployedHash -or $catalogSourceHash -ne $catalogDeployedHash) {
    throw 'The deployed files differ from src. Run scripts\deploy.ps1 again.'
}

$environment = & (Join-Path $PSScriptRoot 'check-environment.ps1') -GameRoot $GameRoot
$testedVersion = '178994'
if ($environment.FileVersion -ne $testedVersion) {
    Write-Warning ("NMS.exe $($environment.FileVersion) is newer or older than the tested $testedVersion. " +
        'All required signatures are checked below; F8 also resolves the game functions again at runtime.')
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
        throw "Hook $hookName has $($result.MatchCount) matches instead of one. Launch stopped safely."
    }
}

if ($PreflightOnly) {
    Write-Host 'Preflight passed. The game was not launched.'
    exit 0
}

Write-Host 'Planetary Surveyor v1.1.0'
Write-Host 'F8 registers the complete fauna, flora, and mineral catalogue for the current planet.'
Write-Host 'No visor, target, or search radius is required. Up to 128 discoveries submit one per second.'
Write-Host 'On foot on a planet, press and release F10 once, then wait until the sounds stop.'
Write-Host "Logs: $projectRoot\logs"
& $pymhf run nmspy
exit $LASTEXITCODE
