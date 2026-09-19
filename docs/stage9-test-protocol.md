# Stage 9 full planet catalogue validation

## Build under test

- No Man's Sky 7.0 Steam, `NMS.exe` file version `178938`;
- NMS.py `178994.0`;
- probe version `1.0.0`;
- full fauna plus resource-manager Flora/Mineral catalogue;
- paced submit interval: one second.

## Procedure

1. Back up the save and launch the game through pyMHF.
2. Stand on a planet without opening the analysis visor.
3. Record the fauna, flora, and mineral counters.
4. Press and release F8 once.
5. Wait until the discovery sounds stop, then re-open Discoveries and compare all
   counters with the log's `accepted_type_counts`.
6. Repeat on a different planet in the same process.

## Confirmed results

First planet:

```text
PlanetObjectCatalogReady resources=78210 matching=151 clusters=10
entries=19 active=17 elapsed=0.551s
unique=26 queued_unknown=23
accepted=23 accepted_type_counts=Animal:6,Flora:6,Mineral:11
```

Second planet:

```text
PlanetObjectCatalogReady resources=78949 matching=159 clusters=10
entries=42 active=28 elapsed=0.742s
unique=56 queued_unknown=56
accepted=56 accepted_type_counts=Animal:14,Flora:24,Mineral:18
```

The user confirmed complete in-game counters on both planets. No visor, target,
travel, or live object spawn was required. Every accepted entry produced one
sound; large per-object HUD cards were absent as expected.

## Stage 9.1 validation (pending)

The resource-manager catalogue was replaced by the planet spawn arrays, the
STEAMVENT/FISHFIENDROCK classifier overrides were added, and the submit queue
gained a focus guard. Test planet: UA `18072676793524483`, where the
exploration-guide quest showed `Flora 8/21, Minerals 15/23` before the test.

Expected from a read-only prototype of the same reader:

```text
PlanetObjectCatalogReady spawn_arrays=10/63/75 entries=49
object catalogue: Flora 26 (9 known), Mineral 23 (15 known)
queued unknown objects: Flora 17, Mineral 8
quest after the queue: Flora 21/21, Minerals 23/23
```

Also check once: switch away with Alt-Tab mid-queue and confirm
`PlanetDiscoverySubmitPaused` and `PlanetDiscoverySubmitResumed` in the log.
