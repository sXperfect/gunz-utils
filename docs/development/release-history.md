# Release History Audit

Audited on 2026-09-28 against repository history, Git refs,
`pyproject.toml`, `CHANGELOG.md`, and GitHub Releases.

## Current state

The package version is `1.11.0`. The annotated tag `v1.11.0` points to
commit `4346b4fb667fcc6fd70c549f8b14188a22a4a780`
(`chore(release): v1.11.0`), so package metadata, changelog, tag, and release
commit are aligned for that version.

There is currently **no GitHub Release object** for `v1.11.0` or for the
historical tags. Publishing a GitHub Release from the existing `v1.11.0` tag
would complete the repository's forward release invariant without changing Git
history.

Post-`v1.11.0` changes remain unreleased and are represented by files under
`changes/`.

## Existing tags

```text
v1.0.0
v1.3.0
v1.3.1
v1.3.2
v1.4.0
v1.5.0
v1.6.0
v1.7.0
v1.8.0
v1.11.0
```

## Untagged historical versions

### 1.1.0

The changelog records 1.1.0, but no `v1.1.0` tag exists. Preserve this as
historical metadata; do not manufacture a tag without independently proving the
intended release commit.

### 1.2.0

Historical release notes state that 1.2.0 was intentionally skipped. No tag
should be created for it.

### 1.9.0

Commit `7ef569bab533` ("feat: add production foundation utilities") changed
the package version from 1.8.0 to 1.9.0 while adding production-foundation APIs.
No dedicated 1.9.0 release tag was created.

Treat 1.9.0 as an untagged development milestone, not as a release to backfill.

### 1.10.0

Commit `276ec6985268` ("build: bump shared-foundation version to 1.10.0")
changed the package version from 1.9.0 to 1.10.0, and commit
`3d3a85e4baa0` later added the 1.10.0 changelog section. No `v1.10.0` tag was
created.

Treat 1.10.0 as an untagged historical milestone. Do not create a retroactive
tag merely to make the sequence contiguous.

## Semantic Versioning history

Some historical 1.x minor versions included removals that would ordinarily be a
major-version change under strict Semantic Versioning. Existing tags and
historical commits are immutable facts and should not be rewritten.

The forward policy is strict:

- incompatible public change or public removal: major;
- backward-compatible public functionality: minor;
- backward-compatible fix/security/performance/docs/internal maintenance: patch.

The release tool enforces the minimum bump encoded by pending fragment
categories.

## Forward invariant

For every newly published release, these values should agree:

```text
pyproject.toml [project].version == X.Y.Z
CHANGELOG.md contains [X.Y.Z]
release commit == chore(release): vX.Y.Z
Git tag == vX.Y.Z
GitHub Release == vX.Y.Z
```

Only `pyproject.toml` stores the package version literal in source. Runtime
package and Sphinx versions are derived from installed package metadata.
