[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sourceRoot = Join-Path $projectRoot 'autoload\native'
$buildRoot = Join-Path $projectRoot 'autoload\build'
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'

if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) {
    throw 'Visual Studio Build Tools were not found.'
}
$vsRoot = & $vswhere -latest -products '*' `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    -property installationPath
if (-not $vsRoot) {
    throw 'MSVC x64 build tools were not found.'
}
$msvcRoot = Get-ChildItem -LiteralPath (Join-Path $vsRoot 'VC\Tools\MSVC') -Directory |
    Sort-Object Name -Descending |
    Select-Object -First 1 -ExpandProperty FullName
$kitsRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10'
$sdkVersion = Get-ChildItem -LiteralPath (Join-Path $kitsRoot 'Include') -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'um\Windows.h') } |
    Sort-Object Name -Descending |
    Select-Object -First 1 -ExpandProperty Name
if (-not $sdkVersion) {
    throw 'Windows 10 SDK headers were not found.'
}

$cl = Join-Path $msvcRoot 'bin\Hostx64\x64\cl.exe'
$link = Join-Path $msvcRoot 'bin\Hostx64\x64\link.exe'
$ml64 = Join-Path $msvcRoot 'bin\Hostx64\x64\ml64.exe'
$savedInclude = $env:INCLUDE
$savedLib = $env:LIB
$savedPath = $env:PATH
try {
    $env:INCLUDE = @(
        (Join-Path $msvcRoot 'include'),
        (Join-Path $kitsRoot "Include\$sdkVersion\ucrt"),
        (Join-Path $kitsRoot "Include\$sdkVersion\shared"),
        (Join-Path $kitsRoot "Include\$sdkVersion\um")
    ) -join ';'
    $env:LIB = @(
        (Join-Path $msvcRoot 'lib\x64'),
        (Join-Path $kitsRoot "Lib\$sdkVersion\ucrt\x64"),
        (Join-Path $kitsRoot "Lib\$sdkVersion\um\x64")
    ) -join ';'
    $env:PATH = (Split-Path -Parent $link) + ';' + $savedPath
    New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
    Push-Location $buildRoot
    try {
        & $cl /nologo /LD /MT /O2 /W4 /WX /DUNICODE /D_UNICODE `
            (Join-Path $sourceRoot 'scanner_bootstrap.c') `
            (Join-Path $sourceRoot 'scanner_ui.c') `
            /link /OUT:PlanetaryDiscoveryScanner.mods
        if ($LASTEXITCODE -ne 0) {
            throw "Native .mods bootstrap build failed with exit code $LASTEXITCODE."
        }
        & $cl /nologo /c /MT /O2 /W4 /WX /DUNICODE /D_UNICODE `
            (Join-Path $sourceRoot 'version_loader.c') /Foversion_loader.obj
        if ($LASTEXITCODE -ne 0) {
            throw "Version loader C build failed with exit code $LASTEXITCODE."
        }
        & $ml64 /nologo /c `
            "/Fo$(Join-Path $buildRoot 'version_forwarders.obj')" `
            (Join-Path $sourceRoot 'version_forwarders.asm')
        if ($LASTEXITCODE -ne 0) {
            throw "Version forwarders build failed with exit code $LASTEXITCODE."
        }
        & $link /nologo /DLL `
            "/DEF:$(Join-Path $sourceRoot 'version_proxy.def')" `
            /OUT:version.dll version_loader.obj version_forwarders.obj
        if ($LASTEXITCODE -ne 0) {
            throw "Version proxy link failed with exit code $LASTEXITCODE."
        }
        & $cl /nologo /MT /O2 /W4 /WX /DUNICODE /D_UNICODE `
            (Join-Path $sourceRoot 'smoke_host.c') /link /SUBSYSTEM:WINDOWS /OUT:smoke_host.exe
        if ($LASTEXITCODE -ne 0) {
            throw "Smoke host build failed with exit code $LASTEXITCODE."
        }
        & $cl /nologo /LD /MT /O2 /W4 /WX /DUNICODE /D_UNICODE `
            (Join-Path $sourceRoot 'smoke_peer.c') /link /OUT:SmokePeer.mods
        if ($LASTEXITCODE -ne 0) {
            throw "Smoke peer build failed with exit code $LASTEXITCODE."
        }
        & $cl /nologo /MT /O2 /W4 /WX /DUNICODE /D_UNICODE `
            (Join-Path $sourceRoot 'installer_launcher.c') `
            /link /SUBSYSTEM:WINDOWS user32.lib /OUT:INSTALL_AUTOLOAD.exe
        if ($LASTEXITCODE -ne 0) {
            throw "Installer launcher build failed with exit code $LASTEXITCODE."
        }
        & $cl /nologo /MT /O2 /W4 /WX /DUNICODE /D_UNICODE /DPDS_UNINSTALL `
            (Join-Path $sourceRoot 'installer_launcher.c') `
            /link /SUBSYSTEM:WINDOWS user32.lib /OUT:UNINSTALL_AUTOLOAD.exe
        if ($LASTEXITCODE -ne 0) {
            throw "Uninstaller launcher build failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    $env:INCLUDE = $savedInclude
    $env:LIB = $savedLib
    $env:PATH = $savedPath
}

Get-Item -LiteralPath `
    (Join-Path $buildRoot 'version.dll'), `
    (Join-Path $buildRoot 'PlanetaryDiscoveryScanner.mods'), `
    (Join-Path $buildRoot 'INSTALL_AUTOLOAD.exe'), `
    (Join-Path $buildRoot 'UNINSTALL_AUTOLOAD.exe'), `
    (Join-Path $buildRoot 'smoke_host.exe'), `
    (Join-Path $buildRoot 'SmokePeer.mods') |
    Select-Object FullName, Length, @{Name = 'SHA256'; Expression = {
        (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    }}
