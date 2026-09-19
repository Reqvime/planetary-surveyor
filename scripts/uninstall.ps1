[CmdletBinding()]
param(
    [string]$GameRoot = ''
)

$ErrorActionPreference = 'Stop'
if (Get-Process -Name NMS -ErrorAction SilentlyContinue) {
    throw 'NMS.exe is running. Close the game normally before uninstalling.'
}
if (-not $GameRoot) {
    $GameRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

$targets = @(
    [pscustomobject]@{
        Path = Join-Path $GameRoot 'GAMEDATA\MODS\discovery_probe.py'
        Marker = 'NMSDiscoveryLab stage-'
    },
    [pscustomobject]@{
        Path = Join-Path $GameRoot 'GAMEDATA\MODS\planet_object_types.py'
        Marker = 'Generated NMS 7.0 scannable object scene hashes'
    }
)

foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target.Path -PathType Leaf)) {
        Write-Host "Already absent: $($target.Path)"
        continue
    }
    if (-not (Select-String -LiteralPath $target.Path -SimpleMatch $target.Marker -Quiet)) {
        throw "$($target.Path) does not carry the NMSDiscoveryLab ownership marker and will not be removed."
    }
    Remove-Item -LiteralPath $target.Path
    Write-Host "Removed: $($target.Path)"
}
