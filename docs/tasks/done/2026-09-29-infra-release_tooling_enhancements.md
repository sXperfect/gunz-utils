# Task: release-tooling-enhancements

**Date:** 2026-09-29
**Role:** Programmer / Tooling Architect
**Component:** `scripts/release.py`, `docs/development/releases.md`, `tests/test_core/test_release_tooling.py`
**Status:** Completed

## 1. Goal

Enhance repository release tooling (`scripts/release.py`) with fragment authoring (`new`), release notes extraction (`notes`), safe tag validation (`tag`), unreleased preview (`unreleased`), and fragment linting for merge conflict markers and formatting.

## 2. Scope

### In Scope

- **`scripts/release.py new`**: CLI/interactive helper to generate properly formatted and validated fragments in `changes/`.
- **`scripts/release.py notes [version]`**: Extractor for version notes from `CHANGELOG.md` to streamline GitHub Releases via `gh release create`.
- **`scripts/release.py tag [--create]`**: Guard and helper validating branch `main`, clean working tree, and `chore(release): vX.Y.Z` commit before creating the tag.
- **`scripts/release.py unreleased`**: Instant stdout view of pending fragments grouped by category section.
- **Fragment Content Linting in `check()`**: Detect conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) and malformed bullets.
- **Unit Tests**: Full unit test coverage in `tests/test_core/test_release_tooling.py`.
- **Documentation**: Update `docs/development/releases.md` and `changes/README.md`.
- **Changelog Fragment**: Created using the new `scripts/release.py new`.

### Out of Scope

- Modifying core package runtime code.
- Auto-pushing to remote origins without explicit operator flag.

## 3. Implementation Steps

1. [x] Implement `new`, `notes`, `tag`, `unreleased`, and fragment linting in `scripts/release.py`.
2. [x] Add unit tests in `tests/test_core/test_release_tooling.py`.
3. [x] Update `docs/development/releases.md` and `changes/README.md`.
4. [x] Create changelog fragment.
5. [x] Run verification suite.
6. [x] Archive task file and update task index.
7. [x] Final commit.

