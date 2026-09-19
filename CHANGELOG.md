# Changelog

## 1.1.0 - 2026-09-19

- Added a native Planetary Discovery Scanner section to the game's Options menu.
  Changes save immediately and coexist with NoMansTime's native settings hook;
  the scanner fails open if a later game patch changes the menu callsite.
- Made Fauna Only the public-package default. All mode remains available for
  best-effort flora and mineral discovery.
- Added `Binaries\PlanetaryDiscoveryScanner.ini` with live-reloaded All/Fauna
  Only mode, 250-1500 ms submit pacing, sound feedback, and hotkey enablement.
  The F1-F12 scan key is selected at game startup.
- Reduced the default submit delay from 1000 ms to 500 ms while preserving the
  game's submit/post-submit sequence. Discovery sound is enabled by default and
  can be disabled in the in-game settings.
- Release packages and the GUI installer now include the settings module and
  preserve an existing user INI during upgrades and removal.
- Added validated runtime layout selection for both the 178938-178994 and
  179105-179292 application layouts. The 179292 game patch shifted the current
  planet, solar-system, and discovery-lookup fields while leaving the called
  functions and generated planet structures intact.
- Added `GameLayoutResolved`/`GameLayoutResolutionFailed` diagnostics and a
  maintainer playbook for separating loader, Python, hook-signature, structure,
  and submit-ABI failures after a game update.

### Earlier development milestones

- First public beta release. Full-planet fauna discovery is the supported core
  feature; flora and mineral discovery remains best effort and can leave entries
  missing on some planets.
- Confirmed the portable launcher and signature resolver in game on executable
  version 178994. A runtime batch accepted 52 entries without submit failures
  (9 fauna, 25 flora, 18 minerals), although the UI counters still demonstrated
  the known flora/mineral catalogue limitation.
- Added the no-console autoload edition. After one GUI installation, the game is
  launched normally from Steam/Epic; bundled Python, pyMHF, NMS.py, and the
  scanner start inside the game process. A clean Steam test loaded 3 mods and 6
  hooks, then accepted 30/30 queued discoveries.
- Added a complete 17-export `version.dll` forwarder for installations without a
  native loader. Compatible existing `*.mods` loaders are preserved; incompatible
  `version.dll` files are never overwritten. The standalone loader was verified
  in the real Steam game: it loaded 3 mods / 6 hooks and submitted 38/38 unknown
  discoveries through the normal F8 path.
- Added GUI install/uninstall launchers, ownership checks, verified atomic copies,
  and a standalone loader smoke test.
- Added a no-installer Manual archive with a direct game-root layout. Its
  optional `version.dll` is kept outside `Binaries`, so extracting the archive
  cannot overwrite another native mod's loader.

- Game function addresses are no longer hard-coded. The first F8 finds them by
  byte signature (also through another mod's detour), so patches that only move
  code keep working. Tested with the 2026-09-15 Steam update (`NMS.exe` 178994).
- Removed the diagnostic submit and populate hooks; they spammed the log and made
  the mod's own hook look like a changed game.
- Discovery timestamps come from the system clock, like the game's `_time64`.
- The launcher warns instead of refusing when the game version differs from the
  tested one; the required signatures are still checked.
- New portable package (`-Portable.zip`): extract into the game folder and
  double-click `PLAY_NMS_WITH_SCANNER.cmd`. It bundles the official embeddable
  Python 3.13 and the pinned NMS.py libraries, downloads nothing, needs no
  administrator rights, and uses no PowerShell. A drop-in `-MODS.zip` serves
  existing NMS.py users.

- Flora and mineral catalogues now come from the current planet's generated
  spawn arrays instead of a resource-manager cluster heuristic. This improves
  coverage substantially, but the game's exact filtering rules are not yet
  fully reproduced.
- Fixed two scene classifier errors found on a `Minerals 17/18` planet:
  underwater steam vents are no longer submitted as minerals, and fish-fiend
  rocks are now included.
- The one-per-second submit queue now pauses while the game window is not in
  the foreground and resumes one interval after focus returns.
- F8 logs spawn scenes missing from the static catalogue, so a scannable type
  the catalogue does not know can be identified from one pass.

## 1.0.0 - 2026-09-15 (internal milestone; not for publication)

- Added the first one-key planet discovery prototype.
- Removed the analysis-visor, target, range, and live-spawn requirements.
- Replaced the old 524,288-slot scene scan with a sub-second resource catalogue
  pass; verified runtime samples completed in 0.551 and 0.742 seconds.
- Added the game's known-discovery filter and a stable one-submit-per-second queue.
- Added strict game-version/signature checks, save backup, installation,
  verification, uninstallation, and release packaging helpers.
- Verified batches of 23 and 56 unknown entries on the initial test planets.
