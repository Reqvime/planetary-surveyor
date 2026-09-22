# Static analysis

Only reproducible Ghidra scripts are tracked here. The Ghidra project, the
local copy of `NMS.exe`, decompiled output, and reports are not committed.

- `InspectPopulateDiscoveryInfo.java` finds the known populate signature,
  lists its direct calls, and decompiles the function.
- `InspectFunctionsByAddress.java` shows entry bytes, callers, direct callees,
  and decompiled output for the given virtual addresses.

Results for `NMS.exe` 178938 are recorded in `docs/findings.md`. Do not assume
the same addresses or signatures apply to another game build.
