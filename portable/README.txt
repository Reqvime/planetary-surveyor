Planetary Discovery Scanner 1.1.1 - portable package
====================================================

Press F10 on a planet to register its fauna, flora, and minerals.
No analysis visor, target, or travelling around the planet is needed.


INSTALL
1. Close No Man's Sky.
2. Extract the PlanetaryDiscoveryScanner folder into your No Man's Sky folder,
   next to Binaries and GAMEDATA.
   (Steam: right-click No Man's Sky > Manage > Browse local files.)
3. Double-click BACKUP_SAVE.cmd once to back up your saves.


PLAY
Double-click PLAY_NMS_WITH_SCANNER.cmd. It starts the game with the mod.
(The Steam Play button starts the game without mods.)
Stand on a planet outside your ship, press and release F10 once, and wait until
the discovery sounds stop. One discovery is sent per second.


WHAT IT DOES TO YOUR PC
- Nothing is installed and nothing is downloaded. Everything the mod needs is
  inside this folder: an official portable Python from python.org (signed by
  the Python Software Foundation) and the NMS.py/pyMHF mod loader.
- When you press PLAY it copies discovery_probe.py and planet_object_types.py
  into GAMEDATA\MODS and writes one small NMS.py settings file:
  %APPDATA%\pymhf\nmspy\pymhf.local.toml
- NMS.py loads Python into the running game. A few antivirus products flag
  that technique in general. The complete source code is public.


UNINSTALL
Double-click UNINSTALL.cmd, then delete this folder.


GOOD TO KNOW
- Fauna is the reliable feature. Flora and minerals are experimental and can
  remain incomplete on some planets even after a repeated F10 press.
- Discoveries cannot be undone one by one; keep your backup.
- Play single-player, preferably in Steam Offline Mode. Disable other scanner
  or discovery mods.
- After a game update F10 may do nothing until the mod is updated; the log then
  contains PlanetDiscoverySubmitBlocked.
- Logs are in the logs folder next to this file.

Unofficial community project; not affiliated with Hello Games. MIT licensed.
