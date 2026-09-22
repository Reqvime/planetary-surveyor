# Release checklist

## Nexus Mods

Upload `dist\Planetary-Surveyor-v1.1.1.zip` as the Main File.

Use `docs/NEXUS_DESCRIPTION.md` as the page description. Do not upload the
developer/source ZIP to Nexus; link the GitHub repository instead.

## GitHub repository

Commit the source tree, tests, build scripts, licence, changelog, and docs. Keep
generated archives, bundled Python, logs, local virtual environments, compiler
output, dumps, and smoke-test directories out of Git; `.gitignore` covers them.

Tag the release commit `v1.1.1` and attach `Planetary-Surveyor-v1.1.1.zip` to
the GitHub Release. GitHub creates source-code archives automatically.

Future work should start from a new feature or development branch. Merge tested
changes back to the stable branch and create a new versioned release branch/tag;
do not rewrite an already published tag.

## Before publishing

1. Back up a save and close NMS.
2. Run the full unit-test suite with `PYTEST_VERSION=1`.
3. Build the player archive with `scripts/build-release.ps1`.
4. Confirm the player ZIP contains no nested archives.
5. Test a clean drag-and-drop install, normal Steam launch, F10, and manual
   removal using the exact public archive.
6. Confirm the newest log contains `GameAddressesResolved result=ok` and no
   submit failure.

## After an NMS update

Test the existing public archive first. A patch that keeps all signatures and
layouts working needs only a compatibility-note update on Nexus/GitHub, not a
new binary upload. Publish a new mod version only when source or bundled runtime
files must change. See `docs/UPDATE_POLICY.md` for the failure conditions and
log checks.
