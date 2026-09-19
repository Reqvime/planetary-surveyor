[CmdletBinding()]
param(
    [string]$Version = '1.1.0',
    # Official Windows embeddable CPython zip matching the .venv minor version.
    [string]$EmbeddablePython = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$distRoot = Join-Path $projectRoot 'dist'
$stageRoot = Join-Path $distRoot ('.stage-' + $Version)
$packageRoot = Join-Path $stageRoot 'NMSDiscoveryLab'
$archive = Join-Path $distRoot ("Planetary-Discovery-Scanner-v$Version.zip")
$modsRoot = Join-Path $stageRoot 'MODS'
$modsArchive = Join-Path $distRoot ("Planetary-Discovery-Scanner-v$Version-MODS.zip")
$portableRoot = Join-Path $stageRoot 'PlanetaryDiscoveryScanner'
$portableArchive = Join-Path $distRoot ("Planetary-Discovery-Scanner-v$Version-Portable.zip")
$autoloadArchive = Join-Path $distRoot ("Planetary-Discovery-Scanner-v$Version-Autoload.zip")
$manualArchive = Join-Path $distRoot ("Planetary-Surveyor-v$Version.zip")
if (-not $EmbeddablePython) {
    $EmbeddablePython = Join-Path $distRoot 'cache\python-3.13.15-embed-amd64.zip'
}

New-Item -ItemType Directory -Path $distRoot -Force | Out-Null
$resolvedDist = (Resolve-Path -LiteralPath $distRoot).Path
$resolvedProject = (Resolve-Path -LiteralPath $projectRoot).Path
if (-not $resolvedDist.StartsWith($resolvedProject + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Release directory escaped the project root.'
}
if (Test-Path -LiteralPath $stageRoot) {
    $resolvedStage = (Resolve-Path -LiteralPath $stageRoot).Path
    if (-not $resolvedStage.StartsWith($resolvedDist + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Staging directory escaped the release directory.'
    }
    Remove-Item -LiteralPath $resolvedStage -Recurse -Force
}

# Batch files must use CRLF; the working tree may hold LF copies.
function Copy-TextWithCrlf([string]$Source, [string]$Destination) {
    $text = [IO.File]::ReadAllText($Source) -replace "`r?`n", "`r`n"
    [IO.File]::WriteAllText($Destination, $text, (New-Object Text.UTF8Encoding($false)))
}

New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
$rootFiles = @('README.md', 'LICENSE', 'CHANGELOG.md', 'pyproject.toml', 'config.example.ps1')
foreach ($file in $rootFiles) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $file) -Destination $packageRoot
}
foreach ($file in 'INSTALL.cmd', 'PLAY_NMS_WITH_SCANNER.cmd', 'VERIFY_INSTALL.cmd', 'BACKUP_SAVE.cmd', 'UNINSTALL.cmd') {
    Copy-TextWithCrlf (Join-Path $projectRoot $file) (Join-Path $packageRoot $file)
}
New-Item -ItemType Directory -Path (Join-Path $packageRoot 'src') | Out-Null
Copy-Item -Path (Join-Path $projectRoot 'src\*.py') -Destination (Join-Path $packageRoot 'src')
New-Item -ItemType Directory -Path (Join-Path $packageRoot 'scripts') | Out-Null
Copy-Item -Path (Join-Path $projectRoot 'scripts\*.ps1') -Destination (Join-Path $packageRoot 'scripts')
Copy-Item -Path (Join-Path $projectRoot 'scripts\*.py') -Destination (Join-Path $packageRoot 'scripts')
Copy-Item -LiteralPath (Join-Path $projectRoot 'docs') -Destination $packageRoot -Recurse
New-Item -ItemType Directory -Path (Join-Path $packageRoot 'tests') | Out-Null
Copy-Item -Path (Join-Path $projectRoot 'tests\*.py') -Destination (Join-Path $packageRoot 'tests')
New-Item -ItemType Directory -Path (Join-Path $packageRoot 'analysis') | Out-Null
Copy-Item -Path (Join-Path $projectRoot 'analysis\*.py') -Destination (Join-Path $packageRoot 'analysis')
Copy-Item -LiteralPath (Join-Path $projectRoot 'analysis\README.md') -Destination (Join-Path $packageRoot 'analysis')
Copy-Item -LiteralPath (Join-Path $projectRoot 'analysis\ghidra_scripts') -Destination (Join-Path $packageRoot 'analysis') -Recurse
New-Item -ItemType Directory -Path (Join-Path $packageRoot 'autoload\native') -Force | Out-Null
Copy-Item -Path (Join-Path $projectRoot 'autoload\*.py') -Destination (Join-Path $packageRoot 'autoload')
Copy-Item -Path (Join-Path $projectRoot 'autoload\*.txt') -Destination (Join-Path $packageRoot 'autoload')
foreach ($pattern in '*.c', '*.h', '*.asm', '*.def') {
    Copy-Item -Path (Join-Path $projectRoot "autoload\native\$pattern") `
        -Destination (Join-Path $packageRoot 'autoload\native')
}

# Drop-in archive for players who already run NMS.py: extract into GAMEDATA\MODS.
New-Item -ItemType Directory -Path $modsRoot -Force | Out-Null
foreach ($file in 'discovery_probe.py', 'planet_object_types.py', 'scanner_settings.py') {
    Copy-Item -LiteralPath (Join-Path $projectRoot "src\$file") -Destination $modsRoot
}
Copy-TextWithCrlf (Join-Path $projectRoot 'docs\MODS_README.txt') `
    (Join-Path $modsRoot 'PlanetaryDiscoveryScanner-README.txt')

# Portable archive: extract into the game folder and double-click PLAY. It bundles
# the official embeddable CPython and the .venv's pinned packages, so nothing is
# installed or downloaded on the player's PC.
$buildPortable = Test-Path -LiteralPath $EmbeddablePython -PathType Leaf
if ($buildPortable) {
    $runtime = Join-Path $portableRoot 'runtime'
    Expand-Archive -LiteralPath $EmbeddablePython -DestinationPath $runtime
    $venvVersion = (Get-Content -LiteralPath (Join-Path $projectRoot '.venv\pyvenv.cfg') |
        Where-Object { $_ -match '^version\s*=' }) -replace '^version\s*=\s*', ''
    $versionParts = $venvVersion.Trim().Split('.')
    $pythonTag = 'python' + $versionParts[0] + $versionParts[1]
    if (-not (Test-Path -LiteralPath (Join-Path $runtime "$pythonTag.dll"))) {
        throw "Embeddable Python does not match the .venv version $venvVersion."
    }
    $stdlibArchive = Join-Path $runtime "$pythonTag.zip"
    $stdlibDir = Join-Path $runtime 'Lib'
    New-Item -ItemType Directory -Path $stdlibDir -Force | Out-Null
    Expand-Archive -LiteralPath $stdlibArchive -DestinationPath $stdlibDir -Force
    Remove-Item -LiteralPath $stdlibArchive

    # Enable the expanded standard library, site-packages, and pywin32.pth.
    $pth = Join-Path $runtime "$pythonTag._pth"
    $pthLines = @(Get-Content -LiteralPath $pth | Where-Object {
        $_ -and -not $_.StartsWith('#') -and $_ -ne "$pythonTag.zip"
    })
    $pthLines += 'Lib'
    $pthLines += 'Lib\site-packages'
    $pthLines += 'import site'
    [IO.File]::WriteAllLines($pth, [string[]]($pthLines | Select-Object -Unique))

    $sitePackages = Join-Path $runtime 'Lib\site-packages'
    New-Item -ItemType Directory -Path $sitePackages -Force | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $projectRoot '.venv\Lib\site-packages') |
        Where-Object { $_.Name -notmatch '^(pip|pip-.*\.dist-info|__pycache__)$' } |
        Copy-Item -Destination $sitePackages -Recurse
    Get-ChildItem -LiteralPath $sitePackages -Recurse -Directory -Filter '__pycache__' |
        Remove-Item -Recurse -Force

    $app = Join-Path $portableRoot 'app'
    New-Item -ItemType Directory -Path (Join-Path $app 'mod') -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot 'portable\app\scanner.py') -Destination $app
    foreach ($file in 'discovery_probe.py', 'planet_object_types.py', 'scanner_settings.py') {
        Copy-Item -LiteralPath (Join-Path $projectRoot "src\$file") -Destination (Join-Path $app 'mod')
    }
    foreach ($file in 'PLAY_NMS_WITH_SCANNER.cmd', 'BACKUP_SAVE.cmd', 'UNINSTALL.cmd', 'README.txt') {
        Copy-TextWithCrlf (Join-Path $projectRoot "portable\$file") (Join-Path $portableRoot $file)
    }
    Copy-TextWithCrlf (Join-Path $projectRoot 'LICENSE') (Join-Path $portableRoot 'LICENSE.txt')
    Copy-TextWithCrlf (Join-Path $projectRoot 'CHANGELOG.md') (Join-Path $portableRoot 'CHANGELOG.md')
}
else {
    Write-Warning "Embeddable Python not found at $EmbeddablePython; the portable package is skipped."
}

$archives = @($archive, $modsArchive)
if ($buildPortable) {
    $archives += $portableArchive
    $archives += $autoloadArchive
    $archives += $manualArchive
}
foreach ($target in $archives) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target
    }
}
# Windows PowerShell 5.1 (Compress-Archive and ZipFile.CreateFromDirectory) writes
# '\' entry separators, which some archivers extract as literal file names.
# Entries are therefore added one by one with standard '/' separators.
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
function New-ZipFromDirectory([string]$Source, [string]$Destination, [string]$Prefix) {
    $root = (Resolve-Path -LiteralPath $Source).Path.TrimEnd('\') + '\'
    $zip = [IO.Compression.ZipFile]::Open($Destination, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in Get-ChildItem -LiteralPath $Source -Recurse -File) {
            $name = $Prefix + $file.FullName.Substring($root.Length).Replace('\', '/')
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $file.FullName, $name, [IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    }
    finally {
        $zip.Dispose()
    }
}
New-ZipFromDirectory $packageRoot $archive 'NMSDiscoveryLab/'
New-ZipFromDirectory $modsRoot $modsArchive ''
if ($buildPortable) {
    New-ZipFromDirectory $portableRoot $portableArchive 'PlanetaryDiscoveryScanner/'

    # Main public package: install once, then use the normal Steam/Epic Play
    # button. The native installer preserves compatible existing version.dll
    # loaders and installs ours only where none exists.
    & (Join-Path $projectRoot 'scripts\build-autoload.ps1') | Out-Host
    $autoloadBuild = Join-Path $projectRoot 'autoload\build'
    $autoloadApp = Join-Path $portableRoot 'app'
    $autoloadLoader = Join-Path $autoloadApp 'loader'
    New-Item -ItemType Directory -Path $autoloadLoader -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $projectRoot 'autoload\autoload_bootstrap.py') `
        -Destination $autoloadApp
    Copy-Item -LiteralPath (Join-Path $projectRoot 'autoload\autoload_installer.py') `
        -Destination $autoloadApp
    Copy-Item -LiteralPath (Join-Path $autoloadBuild 'version.dll') -Destination $autoloadLoader
    Copy-Item -LiteralPath (Join-Path $autoloadBuild 'PlanetaryDiscoveryScanner.mods') `
        -Destination $autoloadLoader
    Copy-Item -LiteralPath (Join-Path $projectRoot 'PlanetaryDiscoveryScanner.ini') `
        -Destination $autoloadLoader
    Copy-Item -LiteralPath (Join-Path $autoloadBuild 'INSTALL_AUTOLOAD.exe') `
        -Destination $portableRoot
    Copy-Item -LiteralPath (Join-Path $autoloadBuild 'UNINSTALL_AUTOLOAD.exe') `
        -Destination $portableRoot
    Copy-TextWithCrlf (Join-Path $projectRoot 'autoload\README.txt') `
        (Join-Path $portableRoot 'README.txt')
    foreach ($legacyLauncher in 'PLAY_NMS_WITH_SCANNER.cmd', 'UNINSTALL.cmd') {
        $legacyPath = Join-Path $portableRoot $legacyLauncher
        if (Test-Path -LiteralPath $legacyPath) {
            Remove-Item -LiteralPath $legacyPath
        }
    }
    New-ZipFromDirectory $portableRoot $autoloadArchive 'PlanetaryDiscoveryScanner/'

    # No-installer package for users who prefer ordinary Nexus-style manual
    # copying. The loader is deliberately kept outside Binaries so extraction
    # can never overwrite another mod's version.dll.
    $manualRoot = Join-Path $stageRoot 'Manual'
    $manualBundle = Join-Path $manualRoot 'PlanetaryDiscoveryScanner'
    $manualBinaries = Join-Path $manualRoot 'Binaries'
    $manualOptionalLoader = Join-Path $manualRoot 'OPTIONAL_LOADER_IF_VERSION_DLL_IS_MISSING'
    Copy-Item -LiteralPath $portableRoot -Destination $manualBundle -Recurse
    foreach ($unusedFile in @(
        'INSTALL_AUTOLOAD.exe',
        'UNINSTALL_AUTOLOAD.exe',
        'BACKUP_SAVE.cmd',
        'README.txt',
        'CHANGELOG.md',
        'LICENSE.txt'
    )) {
        $unusedPath = Join-Path $manualBundle $unusedFile
        if (Test-Path -LiteralPath $unusedPath) {
            Remove-Item -LiteralPath $unusedPath
        }
    }
    $manualInstallerScript = Join-Path $manualBundle 'app\autoload_installer.py'
    if (Test-Path -LiteralPath $manualInstallerScript) {
        Remove-Item -LiteralPath $manualInstallerScript
    }
    $manualEmbeddedLoader = Join-Path $manualBundle 'app\loader'
    if (Test-Path -LiteralPath $manualEmbeddedLoader) {
        Remove-Item -LiteralPath $manualEmbeddedLoader -Recurse -Force
    }
    New-Item -ItemType Directory -Path $manualBinaries, $manualOptionalLoader -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $autoloadBuild 'PlanetaryDiscoveryScanner.mods') `
        -Destination $manualBinaries
    Copy-Item -LiteralPath (Join-Path $projectRoot 'PlanetaryDiscoveryScanner.ini') `
        -Destination $manualBinaries
    Copy-Item -LiteralPath (Join-Path $autoloadBuild 'version.dll') `
        -Destination $manualOptionalLoader
    Copy-TextWithCrlf (Join-Path $projectRoot 'autoload\MANUAL_README.txt') `
        (Join-Path $manualRoot 'README.txt')
    Copy-TextWithCrlf (Join-Path $projectRoot 'LICENSE') `
        (Join-Path $manualRoot 'LICENSE.txt')
    New-ZipFromDirectory $manualRoot $manualArchive ''
}
Remove-Item -LiteralPath $stageRoot -Recurse -Force

$releaseResults = foreach ($target in $archives) {
    [pscustomobject]@{
        Archive = $target
        SHA256 = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        Bytes = (Get-Item -LiteralPath $target).Length
    }
}
$checksumFile = Join-Path $distRoot ("Planetary-Discovery-Scanner-v$Version-SHA256.txt")
$checksumLines = $releaseResults | ForEach-Object {
    "{0}  {1}" -f $_.SHA256, (Split-Path -Leaf $_.Archive)
}
[IO.File]::WriteAllLines(
    $checksumFile,
    [string[]]$checksumLines,
    (New-Object Text.UTF8Encoding($false))
)
$releaseResults
[pscustomobject]@{
    Archive = $checksumFile
    SHA256 = (Get-FileHash -LiteralPath $checksumFile -Algorithm SHA256).Hash
    Bytes = (Get-Item -LiteralPath $checksumFile).Length
}
