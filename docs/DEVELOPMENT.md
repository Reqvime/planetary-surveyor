# Developer guide

## Prerequisites

- Windows x64 and an installed No Man's Sky copy.
- Python 3.13 x64 for the source environment.
- Visual Studio Build Tools with the MSVC x64 compiler and Windows 10 SDK for
  native autoload builds.
- A separate backup of `%APPDATA%\HelloGames\NMS` before runtime tests.

The project dependency is pinned in `pyproject.toml` to `nmspy==178994.0`.

## Repository map

| Path | Purpose |
| --- | --- |
| `src/` | Runtime discovery mod and generated scene classification |
| `autoload/` | Native/Python normal-launch bootstrap and installers |
| `portable/` | Explicit-launch fallback package |
| `scripts/` | Setup, deployment, preflight, native build, and release build |
| `tests/` | Catalogue, identity, signature, focus, and installer regressions |
| `analysis/` | Offline executable and reverse-engineering helpers |
| `docs/HANDOFF.md` | Chronological technical handoff and current research state |
| `docs/findings.md` | Detailed reverse-engineering evidence |
| `docs/stage*-test-protocol.md` | Historical runtime experiment protocols |

Generated archives, embedded runtimes, logs, compiler output, dumps, and local
virtual environments are intentionally excluded by `.gitignore`.

## Setup and developer launch

From the project directory:

```powershell
.\scripts\setup.ps1 -PythonExe "C:\full\path\to\Python313\python.exe"
.\scripts\deploy.ps1
.\scripts\run.ps1 -BackupConfirmed -PreflightOnly
.\scripts\run.ps1 -BackupConfirmed
```

The source workflow is for development only. Public players should use the
single ready-to-install release archive.

## Tests

```powershell
$env:PYTEST_VERSION = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:PYTEST_VERSION
```

One test resolves every required scanner signature against the installed
`..\Binaries\NMS.exe`. Passing offline tests does not replace a backed-up runtime
test after a new game build.

## Native and release builds

```powershell
.\scripts\build-autoload.ps1
.\scripts\build-release.ps1 -Version 1.1.1
```

The full release build needs the matching official embeddable CPython archive at
`dist\cache\python-3.13.15-embed-amd64.zip`, or an explicit
`-EmbeddablePython` path.

Outputs in `dist`:

- `Planetary-Surveyor-v<version>.zip`: ready-to-install player package;
- additional developer and troubleshooting packages used during development.

Only the Planetary Surveyor player package belongs on the public Release page.
GitHub creates source-code archives from the tag automatically.

Run every item in `RELEASE_CHECKLIST.md` before publishing.

## Logs and update triage

Runtime logs are under `PlanetaryDiscoveryScanner\logs`. Start with the newest
`pymhf-*.log`, then `autoload-bootstrap.log`,
`autoload-bootstrap-python.log`, and `version-loader.log` for startup failures.

After an NMS patch:

1. Preserve the public archive and test it unchanged against a backed-up save.
2. Run the signature regression test against the new `NMS.exe`.
3. Require `GameAddressesResolved result=ok` on the first scan request.
4. Require `GameLayoutResolved` and record the selected profile.
5. Compare catalogue sizes, accepted counts, and UI counters on a known planet.
6. Update only the compatibility note when no source/runtime change is needed.
7. Publish a new mod version when signatures, structures, or bundled runtime
   files change.

See `UPDATE_POLICY.md` for the exact compatibility boundary.

## Continuing the unfinished research

The supported v1.1.1 boundary is full fauna plus best-effort flora/minerals.
Future work should focus on the game's remaining flora/mineral filtering and
alias rules, not another radius scan.

Before changing code, read these in order:

1. `ARCHITECTURE.md` for the current data path.
2. The top/current-state sections of `HANDOFF.md`.
3. `findings.md` for evidence and discarded hypotheses.
4. Relevant `stage*-test-protocol.md` files when reproducing an experiment.
5. The newest successful and failing runtime logs from the tester.

Keep new evidence in `HANDOFF.md` and `findings.md`, add an offline regression
before the next live mutation test, and retain the fail-closed signature and
memory validations.

## Branching

Keep `main` stable. Start future work from a feature branch:

```powershell
git switch main
git switch -c feature/flora-mineral-catalog-v2
```

Merge only after tests and a backed-up runtime confirmation. Create a new
versioned release branch and tag; never move a tag that has already been
published.
