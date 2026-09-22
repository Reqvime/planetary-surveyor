Planetary Discovery Scanner 1.1.1 beta - automatic launcher edition
====================================================================

FAUNA: full-planet discovery is the reliable feature.
FLORA / MINERALS: best effort; some planets can retain missing entries.


INSTALL
1. Close No Man's Sky and back up your saves.
2. Put the PlanetaryDiscoveryScanner folder in the No Man's Sky folder,
   next to Binaries and GAMEDATA.
3. Double-click INSTALL_AUTOLOAD.exe once.
4. From then on, launch the game normally through Steam or Epic Games.
5. On foot on a planet, wait a few seconds and press F10 once.

No console, separate game launcher, system Python, download, or administrator
rights are required. The bundled runtime is official embeddable CPython.


OTHER NATIVE MODS
The installer never overwrites an existing Binaries\version.dll. If that DLL
advertises support for *.mods (for example the loader used by NoMansTime), it is
kept and used. If no version.dll exists, this package installs its own minimal
loader. An incompatible existing version.dll stops installation with an error.


GAME UPDATES
The mod resolves the three game functions it calls by byte signature on the
first F10. Small updates that only move code normally keep working without a mod
update. If a signature or an NMS.py structure changes, discovery submission is
blocked instead of using an unverified address. Check logs after an update.

Compatibility verified with NMS.exe 178994 / NMS.py 178994.0. Other executable
versions are not automatically guaranteed even when the game starts normally.


UNINSTALL
Close the game and double-click UNINSTALL_AUTOLOAD.exe. It removes only native
files carrying this package's ownership marker. Existing third-party version.dll
files are left untouched. Afterwards delete the PlanetaryDiscoveryScanner folder.

Logs are stored in PlanetaryDiscoveryScanner\logs.

Use single-player, preferably Steam Offline Mode. Discoveries change the active
save and cannot be individually undone. This unofficial community project is not
affiliated with Hello Games. MIT licensed.
