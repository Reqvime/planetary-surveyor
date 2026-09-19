# Security

The release contains a native loader and an embedded Python runtime. Antivirus
software may flag these files because the mod loads code inside the game
process.

The relevant files are:

- `version.dll`, an optional proxy loader
- `PlanetaryDiscoveryScanner.mods`, the scanner bootstrap
- the embedded CPython runtime and its native modules

The mod has no updater, downloader, telemetry, ads or network code. It does not
replace or patch `NMS.exe`.

All mod source code and build steps are in this repository. If a download is
flagged, compare it with the official GitHub Release or build it yourself.
