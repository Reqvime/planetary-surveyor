# Architecture and data flow

This document explains the release architecture without requiring the full
reverse-engineering history. For exact offsets, signatures, experiments, and
failed approaches, continue with `HANDOFF.md` and `findings.md`.

## End-to-end flow

```text
normal Steam/Epic launch
        |
        v
version.dll or an existing *.mods loader
        |
        v
PlanetaryDiscoveryScanner.mods
        |
        v
bundled CPython 3.13 -> pyMHF -> NMS.py -> discovery_probe.py
        |
        v
current generated planet data in NMS.exe memory
        |
        +---- fauna roles and creature spawns
        +---- flora/mineral planet-object spawn arrays
        |
        v
game IsDiscoveryKnown -> SubmitDiscoveryData -> PostSubmitDiscovery
```

No discovery list is downloaded. Every candidate comes from the current game's
already-generated solar-system and planet structures.

## Loading without an external launcher

On a clean installation, the supplied `Binaries\version.dll` forwards all 17
exports to the real Windows System32 library, then loads
`PlanetaryDiscoveryScanner.mods`. If a compatible loader such as NoMansTime is
already present, it loads the same `.mods` file and the supplied `version.dll`
is not needed.

The native module waits for the game to initialise, loads the bundled
`python313.dll` and `pyrun_injected`, and executes `autoload_bootstrap.py` inside
the NMS process. The bootstrap configures pyMHF/NMS.py against the already-
running process and loads the Python files from `app/mod`.

This is why normal Steam/Epic launch works and why a system Python installation
is unnecessary.

## Where fauna data comes from

`discovery_probe.py` locates the active generated planet in the game's current
`cGcSolarSystem`. It reads the paired creature-role and creature-spawn arrays.
Each pair supplies:

- the planet universe address;
- creature ID;
- procedural seed;
- creature resource scene;
- creature type and rarity.

The mod reproduces the game's fauna discovery identity from those values. The
role and spawn IDs/seeds must agree, array counts and pointers must be sane, and
all memory must be readable. A failed validation blocks that catalogue instead
of guessing. This direct generated list is why fauna can be completed without
waiting for every animal to spawn nearby.

## Where flora and mineral data comes from

The current planet contains three generated object-spawn arrays. Each seeded
entry supplies a resource scene name and procedural seed. The scene name is
normalised and hashed in the same format used by discovery records.

`planet_object_types.py` classifies known scene hashes as Flora or Mineral. The
scanner then builds the two-key discovery identity:

```text
planet universe address + discovery type + procedural seed + scene hash
```

This catalogue is substantially wider than a radius scan, but it does not yet
reproduce every internal filtering/alias rule used by the Discoveries UI. An
unclassified generated scene is logged for later research. That remaining gap
is why flora and mineral completion is advertised as best effort.

## Filtering and submission

Candidates are deduplicated by the same identity fields used by the game's
submit lookup. Before mutation, each candidate is passed to the game's
`IsDiscoveryKnown`; known entries are discarded.

Unknown entries are queued and sent one per second through
`SubmitDiscoveryData`. Accepted entries then call `PostSubmitDiscovery`, which
produces the normal sound/reward-side processing. The queue pauses when NMS is
not the foreground window and rejects another F8 request while active.

Large HUD discovery cards are intentionally not fabricated. Full-planet entries
often have no live scene object to attach to a safe notification.

## Compatibility strategy

The scanner finds `SubmitDiscoveryData`, `PostSubmitDiscovery`, and
`IsDiscoveryKnown` by byte signature on the first F8. NMS.py also installs its
required hooks by signature. Moving a function therefore does not by itself
break the release.

Offsets inside game structures remain version-sensitive. Bounds, pointer,
capacity, planet-address, role/spawn, and memory-readability checks reduce risk,
but a structural game update can still need new code. See `UPDATE_POLICY.md`.

## Important source files

- `src/discovery_probe.py`: scan handler, memory validation, catalogue building,
  known filtering, and submit queue.
- `src/planet_object_types.py`: classified flora/mineral scene hashes.
- `autoload/native/version_loader.c` and `version_forwarders.asm`: clean-game
  native loader.
- `autoload/native/scanner_bootstrap.c`: embedded-Python bootstrap module.
- `autoload/autoload_bootstrap.py`: in-process pyMHF/NMS.py setup.
- `scripts/build-release.ps1`: produces the release archives.
- `tests/`: regression tests plus signature checks against installed NMS.
