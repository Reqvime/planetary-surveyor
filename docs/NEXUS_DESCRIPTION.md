# Planetary Surveyor

Discover the current planet's fauna with one F10 press, plus best-effort flora
and mineral discovery. No analysis visor, target, search radius, or travelling
around the planet is required.

This is a beta release. Fauna is the reliable feature. Flora and minerals can
remain incomplete on some planets because the game applies catalogue rules that
the mod does not yet reproduce exactly.

## Requirements

- No Man's Sky 7.0 on Windows x64 (tested with Steam `NMS.exe` file versions
  `178994` and `179292`; the version number is not a hard launch gate)
- Windows x64
- No separate Python installation or external launcher

This is a runtime mod, not a `.pak`. The archive includes everything it needs,
so the game still starts normally from Steam after installation.

## Installation

1. Back up your saves and close the game.
2. Download `Planetary-Surveyor-v1.1.0.zip`.
3. Extract it into the No Man's Sky folder. This places the runtime folder and
   `Binaries\PlanetaryDiscoveryScanner.mods` directly.
4. If `Binaries\version.dll` does not exist, copy the supplied optional
   `version.dll` there. Never overwrite an existing `version.dll`.
5. Start the game normally from Steam or Epic Games.

This installation runs no installer, CMD, or PowerShell and needs no
administrator rights or separate Python. See `README.txt` in the archive for
exact paths and safe removal.

The package downloads nothing. Steam autoload has been runtime-tested with both
the included loader and a compatible third-party `*.mods` loader. Epic Games
uses the same Windows layout but is not yet runtime-verified.

## Usage

Stand on a planet outside your ship, press and release F10 once, and keep the
game focused while the batch runs. The default 500 ms pacing takes about 28
seconds for 56 unknown entries and discovery sounds are enabled by default.

Use the Planetary Surveyor section in the game's Options menu to choose
Fauna Only (the safe default) or All, 250-1500 ms pacing, sound feedback,
hotkey enablement, and an F1-F12 scan key. Changes save immediately; the game's
Apply button is not required. A changed scan key applies after restarting the
game. The same values can also be edited in
`Binaries\PlanetaryDiscoveryScanner.ini`.

The game's normal post-submit/reward path runs, but large per-object HUD cards
are not shown. Full-planet entries often have no live scene object from which a
safe card can be constructed.

## Important safety notes

- Back up saves. Discovery changes are not individually reversible.
- Flora and mineral completion is not guaranteed in this beta. Repeated F10
  cannot discover an entry that is absent from the generated catalogue.
- Single-player and Steam Offline Mode are recommended. Multiplayer and online
  discovery-service behaviour are untested.
- Do not change planet, reload, or close the game until the sounds stop.
- Disable other scanner/discovery mods.
- NMS.py and the scanner resolve game functions by byte signature. Small updates
  that only move code normally work without a new download. Changed signatures
  fail closed; structure/layout changes still require a compatibility update.

Removal instructions are included in `README.txt`. Delete `version.dll` only if
you installed the supplied copy and no other native mod uses it.

Verified on Steam NMS executable version 178994. A clean normal-Steam launch
through the included `version.dll` started 3 mods / 6 hooks, resolved all game
addresses, and completed a batch of 38/38 accepted discoveries without submit
failures. Full fauna discovery is confirmed; flora/mineral coverage varies by
planet.

For a later NMS patch, first test the unchanged archive with a backed-up save.
If the log still reports `GameAddressesResolved result=ok` and F10 completes a
batch, only this compatibility note needs updating; users do not need a new
download. A new Nexus file is needed only when signatures, hooked code, or game
structure layouts actually change.

Unofficial community project; not affiliated with Hello Games. MIT licensed.
