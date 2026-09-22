# Game update compatibility

Planetary Discovery Scanner is a runtime mod, so no release can truthfully
promise compatibility with every future No Man's Sky executable. The project is
designed to avoid needless updates while failing closed when an unknown change
would make discovery submission unsafe.

## Changes that normally need no mod update

NMS.py/pyMHF locates its frame and state hooks by byte signature. The scanner
also scans the loaded `NMS.exe` on the first F10 for `SubmitDiscoveryData`,
`PostSubmitDiscovery`, and `IsDiscoveryKnown`. It decodes the application-data
pointer from the matched known-check function rather than storing its address.

Therefore a patch that merely moves functions in the executable, or changes
unrelated assets/content, normally keeps working. The visible executable version
is reported for diagnosis but is not itself used as a hard compatibility gate.

## Changes that can require a release

- The instructions inside one of the signature-matched functions change enough
  that the signature no longer matches.
- NMS.py's hook signatures change.
- The layouts of application, solar-system, planet, discovery, or spawn-array
  structures change while their surrounding function signatures remain similar.
- Python/NMS.py runtime requirements change.

Missing signatures prevent their hooks or the scanner's submit path from being
installed. Structure changes are harder to prove automatically; consequently a
new executable build should still be treated as unverified until a maintainer or
user confirms one F10 result and checks the log.

## After an unnoticed game update

1. Back up the save before testing F10.
2. Start the game normally. If it reaches the menu, check the newest
   `PlanetaryDiscoveryScanner\logs\pymhf-*.log`.
3. On the first F10, require `GameAddressesResolved result=ok` before trusting the
   batch. `PlanetDiscoverySubmitBlocked` means no discovery mutation was made.
4. Report the `NMS.exe` file version and the relevant log. A documentation-only
   compatibility confirmation does not require rebuilding the archive; a changed
   signature or layout does.

## Reading the failure layer

Use the first missing or failing checkpoint; do not start by replacing DLLs.

| Evidence | Meaning | Where to investigate |
| --- | --- | --- |
| No fresh `autoload-bootstrap.log` | `PlanetaryDiscoveryScanner.mods` was not loaded | `version.dll`, the `*.mods` loader, and file placement |
| Native log exists but no `pyMHF |` line | Embedded Python did not start | `autoload-bootstrap-python.log` and runtime files |
| `Loaded ... mods and ... hooks` is absent | NMS.py/pyMHF hook signatures changed | newest `pymhf-*.log`, matching NMS.py release |
| `GameAddressesResolved result=..._signature_unresolved` | One of the scanner's three function signatures changed | `_GAME_FUNCTION_SIGNATURES` and `scripts/check-environment.ps1` |
| `GameLayoutResolutionFailed` | Functions still match, but application/solar-system layout changed | `_GAME_LAYOUTS`, a current NMS.py type package, and `PopulateDiscoveryInfo` disassembly |
| Queue is ready but submit throws/fails | Function ABI or discovery data layout changed | submit/post-submit signatures and `_DiscoveryData` |

The loader and Python bootstrap are version-independent more often than the
game-memory layer. A working unrelated native mod only proves that the loader
survived; it does not prove the scanner's offsets are still correct.

## Adding a layout profile safely

Never change an offset only because an address is readable. A candidate profile
must pass all of these read-only checks before F10 can submit anything:

1. `application_data + current_planet_address_offset` contains a nonzero
   universe address.
2. `application_data + solar_system_pointer_offset` points to readable memory.
3. `solar_system + 0x2544` contains between one and six planets.
4. One inline planet at `solar_system + 0x2E30 + index * 0xD9170` contains that
   same universe address at `+0x08`.
5. Fauna arrays have equal plausible counts and object spawn arrays have
   `size <= capacity`.

Add the validated values as a new `_GameLayout` entry, newest first, then run
the tests and a backed-up in-game test. The runtime selector retains old
profiles, so supporting a new build does not deliberately break older builds.

### 2026-09-17 example: executable 179292

The loader, embedded Python, all six NMS.py hooks, and the three scanner
function signatures still worked. F8 stopped at
`planet_catalog_context_unreadable`. Disassembly and read-only live-memory
validation showed three field shifts:

| Field | 178994 | 179292 |
| --- | ---: | ---: |
| Current planet universe address | `0x57A150` | `0x57A160` |
| Solar-system pointer | `0x71AF60` | `0x71AF70` |
| Known-discovery lookup context | `0x849000` | `0x849020` |

The discovery manager (`0x2CE840`), post-submit context (`0x307848`), solar
system, planet, fauna, and object-spawn layouts were unchanged. The scanner now
validates and selects either profile at runtime.

The tested baseline for release 1.1.1 is NMS 7.0 Steam executable versions
178994 and 179292 with NMS.py 178994.0. Epic Games autoload uses the same
mechanism but has not yet received a runtime test.
