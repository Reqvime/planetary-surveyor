# Contributing

Bug reports and pull requests are welcome. Flora and mineral coverage is the
main unfinished part of the project.

Before changing the scanner, read:

1. `docs/ARCHITECTURE.md`
2. `docs/HANDOFF.md`
3. `docs/findings.md`
4. `docs/UPDATE_POLICY.md`

Keep the signature, pointer, bounds and layout checks. Add a regression test for
reproducible fixes and run the full test suite from `BUILDING.md`.

Do not commit saves, personal logs, dumps, built archives, Python runtimes or
compiler output. Runtime tests should use a backed-up save in single-player or
offline mode.
