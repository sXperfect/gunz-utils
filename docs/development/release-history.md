# Release History Audit

Audited on 2026-09-27 against the repository history, existing Git refs,
`pyproject.toml`, and `CHANGELOG.md`.

## Existing tags

The repository currently has these release tags:

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
```

There are currently no GitHub Releases.

## Untagged version history

### 1.1.0

The changelog records 1.1.0, but no `v1.1.0` tag exists. Preserve this as
historical metadata; do not manufacture a tag without independently proving the
intended release commit.

### 1.2.0

Historical release notes state that 1.2.0 was intentionally skipped. No tag
should be created for it.

### 1.9.0

Commit `7ef569bab533` ("feat: add production foundation utilities") changed
the package version from 1.8.0 to 1.9.0 while adding the production-foundation
APIs. No dedicated 1.9.0 changelog section, `v1.9.0` tag, or GitHub Release
was subsequently created.

Treat 1.9.0 as an untagged development milestone, not as a release that should
be backfilled automatically.

### 1.10.0

Commit `276ec6985268` ("build: bump shared-foundation version to 1.10.0")
changed the package version from 1.9.0 to 1.10.0. Commit `3d3a85e4baa0`
later added the 1.10.0 changelog section. The repository currently uses 1.10.0
as its development baseline, but there is no `v1.10.0` tag and no GitHub
Release.

Do not create a historical `v1.10.0` tag as part of this CI/release-management
refactor. The next official release should be prepared using
`scripts/release.py`, reviewed, merged to `main`, verified, and only then
tagged.

## Semantic Versioning history

Some historical 1.x minor releases included removals that would ordinarily be a
major-version change under strict Semantic Versioning. Existing tags are
immutable historical facts and should not be rewritten.

The forward policy is strict:

- incompatible public change or public removal: major;
- backward-compatible public functionality: minor;
- backward-compatible fix/security/performance/docs/internal maintenance: patch.

The release tool enforces the minimum bump encoded by pending fragment
categories so future releases cannot silently repeat the historical mismatch.

## Forward invariant

For every newly published release, these values should agree:

```text
pyproject.toml [project].version == X.Y.Z
CHANGELOG.md contains [X.Y.Z]
Git tag == vX.Y.Z
GitHub Release == vX.Y.Z
```

Only `pyproject.toml` stores the version literal in source. Runtime package and
Sphinx versions are derived from installed package metadata.
