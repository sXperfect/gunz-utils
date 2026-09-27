# Releases

The canonical maintainer workflow is documented in
`docs/development/releases.md`. The key repository rules are:

- `pyproject.toml` is the sole static package-version source.
- Runtime and Sphinx versions are derived from installed package metadata.
- Ordinary changes add a fragment under `changes/`.
- `python scripts/release.py check` validates release metadata.
- `python scripts/release.py status` reports the minimum pending SemVer bump.
- `python scripts/release.py prepare X.Y.Z` assembles `CHANGELOG.md`.
- Release commits use exactly `chore(release): vX.Y.Z`.
- Tags and GitHub Releases are created only after the release commit is merged
  and verified on `main`.

The current tagged version is `v1.11.0`. Its tag points to the matching
`chore(release): v1.11.0` commit. A GitHub Release has not yet been published
for that tag, so that publication step remains operational follow-up rather than
something to reconstruct with a new tag.

The historical audit is kept in
`docs/development/release-history.md`. Historical source versions without
matching tags are not backfilled automatically.
