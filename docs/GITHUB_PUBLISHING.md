# Publishing to GitHub manually

The local repository already contains the history, release branch, and annotated
tag. Do not upload the `dist` directory into the source repository; compiled
archives belong on the GitHub Release page.

## 1. Create the empty repository

1. Sign in to GitHub and choose **New repository**.
2. Suggested name: `planetary-surveyor`.
3. Choose Public if the source should be available to contributors.
4. Do not initialise it with a README, `.gitignore`, or licence. Those files
   already exist locally, and initialising them remotely creates an unnecessary
   unrelated commit.
5. Create the repository and copy its HTTPS URL.

Official reference:
https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository

## 2. Push the prepared source

Open PowerShell in `NMSDiscoveryLab`, replace the URL, and run:

```powershell
git remote add origin https://github.com/YOUR-NAME/planetary-surveyor.git
git push -u origin main
git push origin v1.1.0
```

Before pushing, `git status --short` should print nothing. Do not use
`git push --all`: the local repository retains historical experiment branches
that are useful for research but unnecessary on the public GitHub page.

If `origin` was entered incorrectly:

```powershell
git remote set-url origin https://github.com/YOUR-NAME/Planetary-Discovery-Scanner.git
```

## 3. Create the GitHub Release

1. Open the repository on GitHub and select **Releases**.
2. Select **Draft a new release**.
3. Choose the already-pushed tag `v1.1.0`.
4. Title it `Planetary Surveyor v1.1.0 (Public Beta)`.
5. Paste `docs/RELEASE_NOTES_v1.1.0.md` into the description.
6. Mark it as a pre-release because flora/mineral completion is still
   experimental.
7. Attach `dist\Planetary-Surveyor-v1.1.0.zip`.
8. Save a draft, verify every attachment, then publish.

GitHub automatically adds repository source ZIP/TAR archives for the tag, so the
custom developer ZIP does not need to be attached.

Official reference:
https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository

## 4. Nexus Mods

Use `Planetary-Surveyor-v1.1.0.zip` as the Main File. Use
`NEXUS_DESCRIPTION.md` as the description and link the GitHub repository as
Source/Documentation. If Nexus quarantines the file, send Support the repository
link and point them to `BUILDING.md` and `SECURITY.md`.

## 5. Future updates

Develop on a feature branch from `main`. When a version is tested, merge it to
`main`, create `release/vX.Y.Z`, add an annotated `vX.Y.Z` tag, push those refs,
and create another GitHub Release. Do not replace assets or move a tag after a
published release; publish a new version instead.
