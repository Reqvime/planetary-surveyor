# Publishing updates

This repository is already public at
`https://github.com/Reqvime/planetary-surveyor`.

## Source code

Work from `main`, preferably on a short-lived branch for each change. Run the
tests in `BUILDING.md`, review the diff, then merge or commit the change to
`main`. Never push `dist`, `.venv`, logs, saves or local configuration files.

The older experimental branches are local research history. Do not use
`git push --all`.

## A new version

1. Update the version, README and changelog where needed.
2. Build and test the new package, including a normal game launch with a
   backed-up save.
3. Commit the final source changes and push `main`.
4. Create a new tag such as `v1.1.1` on that commit and push the tag.
5. Create a GitHub Release from that tag. Attach only the ready-to-install
   `Planetary-Surveyor-v1.1.1.zip` and include its SHA-256 digest.
6. Upload the same ZIP to Nexus and update the tested game versions.

Do not move a published version tag or silently replace a release ZIP. If code
or bundled files change, use a new version. A game patch that does not break
the mod may only need an updated compatibility note.

The automatic "Source code (zip)" download on GitHub contains repository
files, not the ready-to-install mod. Players should download the attached
`Planetary-Surveyor-vX.Y.Z.zip` asset.

GitHub release documentation:
https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
