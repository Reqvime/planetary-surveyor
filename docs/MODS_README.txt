Planetary Discovery Scanner 1.1.0 - drop-in files for NMS.py
=============================================================

These three files are an NMS.py (pyMHF) mod:

    discovery_probe.py
    planet_object_types.py
    scanner_settings.py

Requirements: No Man's Sky on Steam with NMS.py already installed and working
(tested with NMS.exe 178994 and NMS.py 178994.0).

Install: put all three .py files in the folder NMS.py loads mods from, normally
    <No Man's Sky>\GAMEDATA\MODS
then start the game the way you start NMS.py (for example `pymhf run nmspy`).

Use: stand on a planet outside your ship, press and release F10 once, and keep
the game focused while it processes. Fauna is the reliable feature.
Flora and mineral discovery is best effort and can remain incomplete on some
planets even after a repeated F8 press.

Back up your saves first: discoveries cannot be undone one by one. Use
single-player, preferably Steam Offline Mode.

If F8 does nothing after a game update, the NMS.py log contains
`PlanetDiscoverySubmitBlocked`; the mod then needs an update.

Settings are created at Binaries\PlanetaryDiscoveryScanner.ini. Mode=FaunaOnly
excludes flora/minerals, SubmitDelayMs controls 250-1500 ms pacing,
SoundFeedback controls repeated sounds, and ScanKey supports F1-F12 after a
restart.

Uninstall: delete the three .py files.
Source, full installer package, and issues: see the project page.
