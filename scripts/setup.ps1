[CmdletBinding()]
param(
    [string]$PythonExe = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$localConfig = Join-Path $projectRoot 'config.local.ps1'
$requestedPythonExe = $PythonExe

if (Test-Path -LiteralPath $localConfig -PathType Leaf) {
    . $localConfig
}
if ($requestedPythonExe) {
    $PythonExe = $requestedPythonExe
}

if (-not $PythonExe) {
    try {
        $PythonExe = (& py -3.13 -c 'import sys; print(sys.executable)' 2>$null | Select-Object -First 1).Trim()
    }
    catch {
        $PythonExe = ''
    }
}

if (-not $PythonExe -or -not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw 'Python 3.13 x64 was not found. Install it from python.org or pass -PythonExe C:\full\path\python.exe.'
}

$inspectPython = @'
import json, platform, sys
print(json.dumps({
    "major": sys.version_info.major,
    "minor": sys.version_info.minor,
    "arch": platform.architecture()[0],
    "exe": sys.executable,
}))
'@
$pythonInfo = & $PythonExe -c $inspectPython
$pythonInfo = $pythonInfo | ConvertFrom-Json
if ($pythonInfo.major -ne 3 -or $pythonInfo.minor -ne 13 -or $pythonInfo.arch -ne '64bit') {
    $found = "$($pythonInfo.major).$($pythonInfo.minor) $($pythonInfo.arch): $($pythonInfo.exe)"
    throw "Python 3.13 x64 is required; found $found"
}

$venvRoot = Join-Path $projectRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    & $PythonExe -m venv $venvRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the virtual environment; exit code $LASTEXITCODE."
    }
}

& $venvPython -m pip install --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to update pip; exit code $LASTEXITCODE."
}
& $venvPython -m pip install --disable-pip-version-check 'nmspy==178994.0'
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install nmspy 178994.0; exit code $LASTEXITCODE."
}

$versionPython = @'
import platform
from importlib.metadata import version
print("Python=" + platform.python_version())
print("nmspy=" + version("nmspy"))
print("pymhf=" + version("pymhf"))
'@
$versions = & $venvPython -c $versionPython
if ($LASTEXITCODE -ne 0) {
    throw "Failed to verify Python package versions; exit code $LASTEXITCODE."
}
$versions

$gameRoot = (Resolve-Path (Join-Path $projectRoot '..')).Path
$modsDirectory = Join-Path $gameRoot 'GAMEDATA\MODS'
$logDirectory = Join-Path $projectRoot 'logs'
$pymhfConfigDirectory = Join-Path $env:APPDATA 'pymhf\nmspy'
$pymhfConfig = Join-Path $pymhfConfigDirectory 'pymhf.local.toml'
New-Item -ItemType Directory -Path $pymhfConfigDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

if (Test-Path -LiteralPath $pymhfConfig -PathType Leaf) {
    $backupName = 'pymhf.local.toml.backup-{0}' -f (Get-Date -Format 'yyyyMMdd-HHmmss')
    Copy-Item -LiteralPath $pymhfConfig -Destination (Join-Path $pymhfConfigDirectory $backupName)
}

$env:NMSDL_PYMHF_CONFIG = $pymhfConfig
$env:NMSDL_MOD_DIRECTORY = $modsDirectory
$env:NMSDL_LOG_DIRECTORY = $logDirectory
try {
    & $venvPython (Join-Path $PSScriptRoot 'configure-pymhf.py')
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to write the pyMHF configuration; exit code $LASTEXITCODE."
    }
}
finally {
    Remove-Item Env:NMSDL_PYMHF_CONFIG -ErrorAction SilentlyContinue
    Remove-Item Env:NMSDL_MOD_DIRECTORY -ErrorAction SilentlyContinue
    Remove-Item Env:NMSDL_LOG_DIRECTORY -ErrorAction SilentlyContinue
}

Write-Host ''
Write-Host "Environment created outside GAMEDATA\MODS: $venvRoot"
Write-Host "Local pyMHF configuration: $pymhfConfig"
Write-Host 'Next step: scripts\deploy.ps1'
