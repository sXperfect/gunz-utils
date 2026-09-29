# Release and Versioning Process

This repository uses a deliberately local-first release process. Release
semantics live in repository code and can be run by a developer or an agent
without depending on a GitHub Actions workflow.

## Invariants

1. `pyproject.toml` is the only static source of the distribution version.
2. `gunz_utils._version` derives the runtime version from installed package
   metadata with `importlib.metadata.version("gunz-utils")`.
3. `gunz_utils.__version__` and historical module-level `__version__`
   attributes import that shared resolver for backward compatibility.
4. Sphinx derives its release string from the same installed metadata.
5. Individual modules must never store independent package-version literals.
6. Every user-visible change is represented by a changelog fragment under
   `changes/`.
7. `CHANGELOG.md` is assembled from fragments only when a release is prepared.
8. Releases use strict Semantic Versioning: `MAJOR.MINOR.PATCH`.
9. A release commit uses exactly `chore(release): vX.Y.Z`.
10. A released version should have matching package metadata, changelog heading,
   Git tag `vX.Y.Z`, and GitHub Release `vX.Y.Z`.

## Normal development

Do not edit the top of `CHANGELOG.md` for an ordinary feature or fix. Add one
small fragment instead:

```bash
python scripts/release.py new -c <category> -m "<description>"
```

Or manually create:

```text
changes/<unique-id>.added.md
changes/<unique-id>.fixed.md
changes/<unique-id>.breaking.md
```

A pull-request number is a useful ID when one exists. For work done before a PR,
use a stable descriptive ID. IDs must be unique across pending fragments.

Supported fragment categories are documented in
[`changes/README.md`](../../changes/README.md). The strongest pending category
determines the minimum allowed release bump:

| Fragment | Minimum release impact |
|---|---|
| `breaking`, `removed` | major |
| `added`, `changed`, `deprecated` | minor |
| `security`, `fixed`, `performance`, `docs`, `internal` | patch |

Before merging a normal change:

```bash
python scripts/release.py check
python scripts/ci.py all
```

`check` validates metadata, fragment names, and absence of unresolved merge conflicts.

## Inspect pending release impact

```bash
# View current version, latest tag, fragment counts, and minimum bump
python scripts/release.py status

# Render formatted unreleased changelog markdown
python scripts/release.py unreleased
```

The command reports the current package version, the latest available Git tag,
pending fragment counts, repository inconsistencies, and the minimum Semantic
Versioning bump implied by those fragments.

## Prepare a release

Preview the release without mutating any files:

```bash
python scripts/release.py prepare --dry-run
```

Prepare the release automatically (or with an explicit version `X.Y.Z`):

```bash
python scripts/release.py prepare auto
# or: python scripts/release.py prepare 1.12.0
```

Preparation is intentionally a working-tree operation. It:

1. validates repository release metadata;
2. rejects a target smaller than the required Semantic Versioning bump;
3. updates only `[project].version` in `pyproject.toml`;
4. renders pending fragments into a dated `CHANGELOG.md` release section;
5. consumes the fragment files;
6. leaves commit, tag, push, and publication explicit.

Run the full local gate after preparation:

```bash
python scripts/ci.py all
python scripts/release.py verify
```

Then commit the prepared release using exactly:

```text
chore(release): vX.Y.Z
```

The release commit should go through the same pull-request-to-`main` policy as
other changes. Do not create the tag before the release commit is on `main`
and verified.

## Publish

After the release commit is present and verified on `main`, validate release readiness:

```bash
python scripts/release.py tag
```

To create the verified annotated tag:

```bash
python scripts/release.py tag --create
git push origin vX.Y.Z
```

Extract the release notes directly for GitHub Releases:

```bash
python scripts/release.py notes | gh release create vX.Y.Z -t "vX.Y.Z" -F -
```

The release tooling deliberately does not push, tag, publish packages, or create
GitHub Releases automatically without explicit flags. Those are explicit operations so an accidental local command
cannot publish a release.

## Historical versions

The repository has historical version metadata that was not always paired with
tags or GitHub Releases. Do not invent tags retroactively merely to make history
look uniform. See
[`release-history.md`](release-history.md) for the audited state and the
forward policy.
