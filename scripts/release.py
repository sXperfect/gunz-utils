# gunz-style: ignore-file[GS010,GS011]
#!/usr/bin/env python3
"""Deterministic local release and changelog tooling.

This module is intentionally standard-library only. It is the canonical place
for release metadata checks and release preparation; GitHub Actions only calls
into it and does not contain independent versioning logic.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import argparse
import ast
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

CATEGORY_ORDER = (
    "breaking",
    "security",
    "added",
    "changed",
    "deprecated",
    "fixed",
    "removed",
    "performance",
    "docs",
    "internal",
)
CATEGORY_TITLES = {
    "breaking": "Breaking",
    "security": "Security",
    "added": "Added",
    "changed": "Changed",
    "deprecated": "Deprecated",
    "fixed": "Fixed",
    "removed": "Removed",
    "performance": "Performance",
    "docs": "Documentation",
    "internal": "Internal",
}
CATEGORY_BUMP = {
    "breaking": "major",
    "security": "patch",
    "added": "minor",
    "changed": "minor",
    "deprecated": "minor",
    "fixed": "patch",
    "removed": "major",
    "performance": "patch",
    "docs": "patch",
    "internal": "patch",
}
BUMP_RANK = {"none": 0, "patch": 1, "minor": 2, "major": 3}
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
HEADING = re.compile(r"^## \[([^]\n]+)\](?:[^\n]*)$", re.MULTILINE)
FRAGMENT_HEADING = re.compile(r"^ {0,3}#{1,2}(?:[ \t]|$)", re.MULTILINE)
SETEXT_HEADING = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
CONFLICT = re.compile(r"^(?:<{7}|={7}|>{7})(?:\s|$)", re.MULTILINE)
UNRELEASED_NOTE = (
    "Unreleased changes are collected as conflict-free fragments in `changes/`.\n"
    "Run `python scripts/release.py status` to inspect their release impact."
)


class ReleaseError(ValueError):
    """Invalid metadata or a release operation that cannot safely proceed."""


@dataclass(frozen=True, order=True)
class SemVer:
    """A strict MAJOR.MINOR.PATCH semantic version."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls,
        value: str,
    ) -> SemVer:
        """Parse a version without prerelease or leading-zero components."""
        match = SEMVER.fullmatch(value.strip())
        if match is None:
            raise ReleaseError(
                f"invalid version {value!r}; expected strict MAJOR.MINOR.PATCH"
            )
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class Fragment:
    """One validated pending changelog entry."""

    identifier: str
    category: str
    text: str
    path: Path


@dataclass(frozen=True)
class CheckResult:
    """Repository release-consistency result."""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def __iter__(self):
        """Allow tuple unpacking: errors, warnings = repo.check()."""
        return iter((list(self.errors), list(self.warnings)))


def minimum_target(
    current: SemVer,
    bump: str,
) -> SemVer:
    """Return the minimum version satisfying the requested release impact."""
    if bump == "major":
        return SemVer(current.major + 1, 0, 0)
    if bump == "minor":
        return SemVer(current.major, current.minor + 1, 0)
    return SemVer(current.major, current.minor, current.patch + 1)


def required_bump(
    fragments: Iterable[Fragment],
) -> str:
    """Choose the strongest pending category."""
    return max(
        (CATEGORY_BUMP[fragment.category] for fragment in fragments),
        key=BUMP_RANK.__getitem__,
        default="none",
    )


def target_satisfies(
    current: SemVer,
    target: SemVer,
    bump: str,
) -> bool:
    """Return True if target satisfies the minimum required bump."""
    if target <= current:
        return False
    if bump == "major":
        return target.major > current.major
    if bump == "minor":
        return target.major > current.major or (
            target.major == current.major and target.minor > current.minor
        )
    return target > current


def validate_fragment_text(
    text: str,
    name: str,
) -> None:
    """Reject empty entries, conflicts, and headings reserved for releases."""
    if not text:
        raise ReleaseError(f"empty changelog fragment: {name}")
    if CONFLICT.search(text):
        raise ReleaseError(
            f"changelog fragment {name} contains unresolved git conflict markers"
        )
    lines = text.splitlines()
    setext_heading = any(
        previous.strip() and SETEXT_HEADING.fullmatch(line)
        for previous, line in zip(lines, lines[1:], strict=False)
    )
    if FRAGMENT_HEADING.search(text) or setext_heading:
        raise ReleaseError(
            f"unsupported release-level heading in fragment: {name}; "
            "use prose, bullets, or headings at level 3 or deeper"
        )


def project_version(
    text: str,
) -> SemVer:
    """Read and validate the project version from complete TOML contents."""
    data = tomllib.loads(text)
    project = data.get("project")
    value = project.get("version") if isinstance(project, dict) else None
    if not isinstance(value, str):
        raise ReleaseError("missing pyproject.toml [project].version")
    return SemVer.parse(value)


def project_metadata(
    text: str,
) -> tuple[str, SemVer]:
    """Read and validate the project name and version from TOML contents."""
    data = tomllib.loads(text)
    project = data.get("project")
    if not isinstance(project, dict):
        raise ReleaseError("missing pyproject.toml [project] table")
    name = project.get("name")
    if not isinstance(name, str) or not name.strip():
        name = "gunz-utils"
    value = project.get("version")
    if not isinstance(value, str):
        raise ReleaseError("missing pyproject.toml [project].version")
    return name, SemVer.parse(value)


def changelog_errors(
    text: str,
    current: SemVer,
) -> list[str]:
    """Validate complete changelog contents against their project version."""
    errors: list[str] = []
    headings = [match[1] for match in HEADING.finditer(text)]
    if not headings or headings[0] != "Unreleased":
        errors.append("CHANGELOG.md must start with a [Unreleased] section")
    if len(headings) != len(set(headings)):
        errors.append("duplicate CHANGELOG.md version heading")
    for value in headings:
        if value != "Unreleased":
            try:
                version = SemVer.parse(value)
            except ReleaseError as exc:
                errors.append(str(exc))
            else:
                if version > current:
                    errors.append(f"changelog version {value} is newer than {current}")
    if CONFLICT.search(text):
        errors.append("CHANGELOG.md contains unresolved conflict markers")
    return errors


def atomic_write(
    path: Path,
    text: str,
) -> None:
    """Replace one file after its complete UTF-8 contents have been flushed."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            prefix=f".{path.name}.",
            suffix=".release-tmp",
        ) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if path.exists():
            temporary.chmod(path.stat().st_mode & 0o777)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class ReleaseRepo:
    """Release operations on one explicit local repository root."""

    def __init__(self,
        root: Path,
    ) -> None:
        self.root = root.resolve()
        self.pyproject = self.root / "pyproject.toml"
        self.changelog = self.root / "CHANGELOG.md"
        self.fragments_dir = self.root / "changes"
        self._project_name: str | None = None

    @property
    def project_name(self) -> str:
        """Resolve the project name from pyproject.toml."""
        if self._project_name is None:
            if self.pyproject.is_file():
                try:
                    self._project_name = project_metadata(
                        self.pyproject.read_text(encoding="utf-8")
                    )[0]
                except (OSError, ValueError):
                    self._project_name = "gunz-utils"
            else:
                self._project_name = "gunz-utils"
        return self._project_name

    @property
    def source_dir(self) -> Path:
        """Path to main package source directory under src/."""
        package_dir = self.project_name.replace("-", "_")
        return self.root / "src" / package_dir

    @property
    def version_module(self) -> Path:
        """Path to _version.py module."""
        return self.source_dir / "_version.py"

    @property
    def init_py(self) -> Path:
        """Path to package __init__.py."""
        return self.source_dir / "__init__.py"

    @property
    def sphinx_conf(self) -> Path:
        """Path to Sphinx documentation configuration."""
        return self.root / "docs" / "source" / "conf.py"

    def current_version(self) -> SemVer:
        """Read the only static package-version source."""
        return project_version(self.pyproject.read_text(encoding="utf-8"))

    def fragments(self) -> list[Fragment]:
        """Validate fragment names, unique IDs, contents, and conflict markers."""
        if not self.fragments_dir.is_dir():
            raise ReleaseError("missing changes/ directory")
        result: list[Fragment] = []
        seen: set[str] = set()
        for path in sorted(self.fragments_dir.iterdir()):
            if path.name == "README.md" or path.name.startswith("."):
                continue
            if not path.is_file() or not path.name.endswith(".md"):
                raise ReleaseError(f"unexpected fragment entry: {path.name}")
            parts = path.name[:-3].rsplit(".", 1)
            if len(parts) != 2 or IDENTIFIER.fullmatch(parts[0]) is None:
                raise ReleaseError(f"invalid fragment filename: {path.name}")
            identifier, category = parts
            if category not in CATEGORY_BUMP:
                raise ReleaseError(f"invalid fragment category: {path.name}")
            if identifier in seen:
                raise ReleaseError(f"duplicate fragment id (ID): {identifier}")
            text = path.read_text(encoding="utf-8").strip()
            validate_fragment_text(text, path.name)
            seen.add(identifier)
            result.append(Fragment(identifier, category, text, path))
        return result

    @staticmethod
    def required_bump(
        fragments: Iterable[Fragment],
    ) -> str:
        """Choose the strongest pending category."""
        return required_bump(fragments)

    @staticmethod
    def minimum_target(
        current: SemVer,
        bump: str,
    ) -> SemVer:
        """Return the minimum version satisfying the requested release impact."""
        return minimum_target(current, bump)

    @staticmethod
    def target_satisfies(
        current: SemVer,
        target: SemVer,
        bump: str,
    ) -> bool:
        """Return True if target satisfies the minimum required bump."""
        return target_satisfies(current, target, bump)

    def _git(self,
        *args: str,
    ) -> str:
        """Run a bounded, shell-free local Git command."""
        result = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode:
            raise ReleaseError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def tags(self) -> list[SemVer]:
        """Read available local tags; metadata checks also work without Git."""
        try:
            text = self._git("tag", "--list", "v*")
        except (OSError, subprocess.TimeoutExpired, ReleaseError):
            return []
        tags: list[SemVer] = []
        for line in text.splitlines():
            val = line.strip()
            if val.startswith("v") and SEMVER.fullmatch(val[1:]):
                try:
                    tags.append(SemVer.parse(val[1:]))
                except ReleaseError:
                    continue
        return sorted(set(tags))

    def _git_tags(self) -> list[SemVer]:
        """Backward-compatibility alias for tags()."""
        return self.tags()

    def check(self) -> CheckResult:
        """Return metadata errors and advisory release-history warnings."""
        errors: list[str] = []
        warnings: list[str] = []
        try:
            current = self.current_version()
        except (OSError, ValueError) as exc:
            return CheckResult((str(exc),), ())

        try:
            fragments = self.fragments()
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            fragments = []

        try:
            changelog = self.changelog.read_text(encoding="utf-8")
            errors.extend(changelog_errors(changelog, current))
        except OSError as exc:
            errors.append(f"missing CHANGELOG.md: {exc}")

        source = self.source_dir
        proj_name = self.project_name
        resolver = self.version_module
        if not resolver.is_file():
            errors.append(f"missing {resolver.relative_to(self.root)}")
        else:
            resolver_text = resolver.read_text(encoding="utf-8")
            if f'metadata.version("{proj_name}")' not in resolver_text:
                errors.append(
                    f"runtime version must use installed {proj_name} metadata"
                )

        if self.init_py.is_file():
            init_text = self.init_py.read_text(encoding="utf-8")
            if (
                "from ._version import __version__" not in init_text
                and "__version__ = _resolve_package_version()" not in init_text
            ):
                rel = self.init_py.relative_to(self.root)
                errors.append(f"{rel} must use the shared version resolver")

        if source.is_dir():
            for path in sorted(source.rglob("*.py")):
                if "_vendor" in path.parts:
                    continue
                try:
                    tree = ast.parse(
                        path.read_text(encoding="utf-8"), filename=str(path)
                    )
                except (OSError, SyntaxError) as exc:
                    errors.append(f"cannot parse {path.relative_to(self.root)}: {exc}")
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                        continue
                    targets = (
                        node.targets if isinstance(node, ast.Assign) else [node.target]
                    )
                    if not any(
                        isinstance(target, ast.Name) and target.id == "__version__"
                        for target in targets
                    ):
                        continue
                    if isinstance(node.value, ast.Constant) and not (
                        path == resolver and node.value.value == "0+unknown"
                    ):
                        rel_path = path.relative_to(self.root)
                        errors.append(
                            f"independent __version__ literal: {rel_path} "
                            "contains a package __version__ literal"
                        )

        if self.sphinx_conf.is_file():
            conf_text = self.sphinx_conf.read_text(encoding="utf-8")
            static_release = re.search(
                r"^release\s*=\s*['\"]\d+\.\d+\.\d+['\"]",
                conf_text,
                re.MULTILINE,
            )
            if static_release is not None:
                errors.append("docs/source/conf.py contains a static release version")
            if f'package_version("{proj_name}")' not in conf_text:
                errors.append(
                    "Sphinx release must derive from installed package metadata"
                )

        tags = self.tags()
        if tags:
            latest = tags[-1]
            if latest > current:
                errors.append(f"latest tag v{latest} is newer than {current}")
            elif current not in tags:
                warnings.append(
                    f"pyproject version {current} has no matching tag; latest tag is "
                    f"v{latest}"
                )
        else:
            warnings.append(
                "No local release tags available; history was not inferred"
            )

        bump = required_bump(fragments)
        if bump != "none":
            warnings.append(
                f"current fragments require at least a {bump} release "
                f"(minimum {minimum_target(current, bump)})"
            )

        return CheckResult(tuple(errors), tuple(warnings))

    def changed_files(self,
        base: str,
    ) -> list[str]:
        """Return paths changed on this branch relative to base revision."""
        if not base:
            raise ReleaseError("check-fragment requires a --base revision")
        text = self._git(
            "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"
        )
        return [line for line in text.splitlines() if line]

    def check_fragment(self,
        base: str,
    ) -> tuple[list[str], list[str]]:
        """Return errors and warnings for changelog coverage of source changes."""
        errors: list[str] = []
        warnings: list[str] = []
        changed = self.changed_files(base)
        src_changed = [
            path
            for path in changed
            if path.startswith("src/") and "_vendor" not in path
        ]
        if not src_changed:
            return errors, warnings
        added = self._git(
            "diff", "--name-only", "--diff-filter=A", f"{base}...HEAD"
        ).splitlines()
        added_fragments = [
            path
            for path in added
            if path.startswith("changes/")
            and path.endswith(".md")
            and Path(path).name != "README.md"
        ]
        if not added_fragments:
            errors.append(
                "source changes under src/ without a changelog fragment; add "
                "one under changes/ (internal-only changes may use the "
                "'internal' category)"
            )
        return errors, warnings

    def report(self,
        *,
        status: bool = False,
    ) -> int:
        """Print metadata diagnostics and optionally pending release counts."""
        result = self.check()
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        if not result.ok:
            return 1
        if status:
            current = self.current_version()
            fragments = self.fragments()
            tags = self.tags()
            counts = Counter(fragment.category for fragment in fragments)
            req = required_bump(fragments)
            print(f"Current version:       {current}")
            if tags:
                print(f"Latest Git tag:        v{tags[-1]}")
            else:
                print("Latest Git tag:        unavailable")
            print(f"Unreleased fragments:  {len(fragments)}")
            for category in CATEGORY_ORDER:
                if counts[category]:
                    print(f"  {category:<12} {counts[category]}")
            if req == "none":
                print("Minimum SemVer bump:   none")
            else:
                print(
                    f"Minimum SemVer bump:   {req} "
                    f"(>= {minimum_target(current, req)})"
                )
        else:
            print("release metadata check: OK")
        return 0

    def check_command(self) -> int:
        """Backward-compatibility alias for report(status=False)."""
        return self.report(status=False)

    def status(self) -> int:
        """Backward-compatibility alias for report(status=True)."""
        return self.report(status=True)

    @staticmethod
    def render(
        fragments: list[Fragment],
    ) -> str:
        """Render deterministic public notes; consume internal entries silently."""
        grouped: dict[str, list[str]] = defaultdict(list)
        for fragment in fragments:
            lines = fragment.text.splitlines()
            entry = (
                fragment.text
                if fragment.text.startswith("- ")
                else ("- " + lines[0] + "".join(f"\n  {line}" for line in lines[1:]))
            )
            grouped[fragment.category].append(entry)
        sections = []
        for category in CATEGORY_ORDER:
            if category != "internal" and grouped[category]:
                sections.append(
                    f"### {CATEGORY_TITLES[category]}\n\n"
                    + "\n\n".join(grouped[category])
                )
        fallback = (
            "### Internal\n\n"
            "- Internal-only maintenance; no user-facing changelog entries."
        )
        return "\n\n".join(sections) or fallback

    def _updated_pyproject(self,
        target: SemVer,
    ) -> str:
        """Replace only the top-level project version, retaining other TOML."""
        text = self.pyproject.read_text(encoding="utf-8")
        section = re.search(r"(?ms)^\[project\][ \t]*\n(.*?)(?=^\[|\Z)", text)
        if section is None:
            raise ReleaseError("cannot locate [project] section")
        body, count = re.subn(
            r"(?m)^(version[ \t]*=[ \t]*)([\"'])[^\"']+\2([ \t]*(?:#.*)?)$",
            lambda match: f'{match[1]}"{target}"{match[3]}',
            section[1],
            count=1,
        )
        if count != 1:
            raise ReleaseError("cannot update [project].version")
        updated = text[: section.start(1)] + body + text[section.end(1) :]
        if tomllib.loads(updated)["project"]["version"] != str(target):
            raise ReleaseError("updated project version did not round-trip")
        return updated

    @staticmethod
    def _validate_prepared(
        pyproject: str,
        changelog: str,
        target: SemVer,
        previous_headings: list[str],
    ) -> None:
        """Validate the complete candidate before writes or fragment removal."""
        current = project_version(pyproject)
        errors = changelog_errors(changelog, current)
        if current != target:
            errors.append(f"prepared project version {current} does not match {target}")
        headings = [match[1] for match in HEADING.finditer(changelog)]
        if headings != ["Unreleased", str(target), *previous_headings[1:]]:
            errors.append(
                "prepared CHANGELOG.md must add exactly one release heading "
                f"for {target}"
            )
        if errors:
            raise ReleaseError("invalid prepared release: " + "; ".join(errors))

    def prepare(self,
        target_text: str = "auto",
        *,
        dry_run: bool = False,
    ) -> int:
        """Validate and prepare local release files; never commit, tag, or push."""
        if self.report():
            return 1
        current = self.current_version()
        fragments = self.fragments()
        if not fragments:
            raise ReleaseError("no changelog fragments to release")
        minimum = minimum_target(current, required_bump(fragments))
        target = minimum if target_text == "auto" else SemVer.parse(target_text)
        if not target_satisfies(current, target, required_bump(fragments)):
            raise ReleaseError(
                f"{target} is too small for {required_bump(fragments)} changes; "
                f"minimum allowed target is {minimum}"
            )
        old_changelog = self.changelog.read_text(encoding="utf-8")
        headings = list(HEADING.finditer(old_changelog))
        if any(match[1] == str(target) for match in headings):
            raise ReleaseError(f"release {target} already appears in CHANGELOG.md")
        end = headings[1].start() if len(headings) > 1 else len(old_changelog)
        manual_notes = old_changelog[headings[0].end() : end].strip("\n")
        if manual_notes == UNRELEASED_NOTE:
            manual_notes = ""
        elif manual_notes.startswith(UNRELEASED_NOTE + "\n"):
            manual_notes = manual_notes[len(UNRELEASED_NOTE) :].lstrip("\n")
        rendered_body = self.render(fragments)
        notes = (
            "\n\n".join(part for part in (manual_notes, rendered_body) if part)
        )
        release_text = (
            f"## [{target}] — {dt.date.today().isoformat()}\n\n"
            f"{notes}\n\n"
        )
        updated = {
            self.pyproject: self._updated_pyproject(target),
            self.changelog: (
                old_changelog[: headings[0].start()]
                + f"## [Unreleased]\n\n{UNRELEASED_NOTE}\n\n"
                + release_text
                + old_changelog[end:]
            ),
        }
        self._validate_prepared(
            updated[self.pyproject],
            updated[self.changelog],
            target,
            [match[1] for match in headings],
        )
        if dry_run:
            req_bump = required_bump(fragments)
            print(f"[DRY-RUN] Target version: {target} (bump: {req_bump})")
            print(f"[DRY-RUN] Fragments consumed ({len(fragments)}):")
            for frag in fragments:
                print(f"  - {frag.path.name}")
            print("\n[DRY-RUN] Proposed CHANGELOG.md addition:")
            print("-" * 60)
            print(f"## [{target}] — {dt.date.today().isoformat()}\n\n{notes}")
            print("-" * 60)
            print("[DRY-RUN] No files modified and no fragments deleted.")
            return 0
        originals = {path: path.read_text(encoding="utf-8") for path in updated}
        originals.update(
            {
                fragment.path: fragment.path.read_text(encoding="utf-8")
                for fragment in fragments
            }
        )
        changed: list[Path] = []
        try:
            for path, text in updated.items():
                atomic_write(path, text)
                changed.append(path)
            for fragment in fragments:
                fragment.path.unlink()
                changed.append(fragment.path)
        except OSError:
            for path in reversed(changed):
                atomic_write(path, originals[path])
            raise
        print(f"Prepared release {target}.")
        print(f"Recommended commit: chore(release): v{target}")
        print(
            f"After merge and verification, create tag v{target} and a matching "
            "GitHub Release."
        )
        return 0

    def verify(self) -> int:
        """Require a prepared version with no remaining fragments."""
        if self.report():
            return 1
        if self.fragments():
            print(
                "ERROR: pending fragments remain; run prepare before verify",
                file=sys.stderr,
            )
            return 1
        version = str(self.current_version())
        headings = [
            match[1]
            for match in HEADING.finditer(self.changelog.read_text(encoding="utf-8"))
        ]
        if len(headings) < 2 or headings[1] != version:
            print(
                f"ERROR: latest changelog release must match {version}",
                file=sys.stderr,
            )
            return 1
        print(f"release {version} is ready for commit/tag verification")
        print(f"expected commit message: chore(release): v{version}")
        print(f"expected tag: v{version}")
        return 0

    def new(self,
        identifier: str | None,
        category: str,
        message: str,
    ) -> int:
        """Create an exclusive, validated fragment without overwriting an ID."""
        text = message.strip()
        validate_fragment_text(text, identifier or "new message")
        if identifier is None:
            slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]
            identifier = f"{dt.date.today():%Y%m%d}-{slug or 'change'}"
        if IDENTIFIER.fullmatch(identifier) is None or category not in CATEGORY_BUMP:
            raise ReleaseError("invalid fragment ID or category")
        if any(fragment.identifier == identifier for fragment in self.fragments()):
            raise ReleaseError(f"fragment ID already exists: {identifier}")
        path = self.fragments_dir / f"{identifier}.{category}.md"
        with path.open("x", encoding="utf-8") as stream:
            lines = text.splitlines()
            formatted = (
                text
                if text.startswith("- ")
                else ("- " + lines[0] + "".join(f"\n  {line}" for line in lines[1:]))
            )
            stream.write(formatted + "\n")
        print(f"Created {path.relative_to(self.root)}")
        return 0

    def new_fragment(self,
        category: str,
        message: str,
        identifier: str | None = None,
    ) -> int:
        """Backward-compatibility alias for new()."""
        return self.new(identifier, category, message)

    def notes(self,
        version_text: str | None = None,
    ) -> int:
        """Print one prepared release's public notes."""
        version = str(
            self.current_version()
            if version_text is None
            else SemVer.parse(version_text)
        )
        text = self.changelog.read_text(encoding="utf-8")
        headings = list(HEADING.finditer(text))
        for index, match in enumerate(headings):
            if match[1] == version:
                end = (
                    headings[index + 1].start()
                    if index + 1 < len(headings)
                    else len(text)
                )
                print(text[match.end() : end].strip())
                return 0
        raise ReleaseError(f"no changelog release for {version}")

    def unreleased(self) -> int:
        """Render pending fragments in changelog format."""
        fragments = self.fragments()
        if not fragments:
            print("No unreleased fragments in changes/.")
            return 0
        print(self.render(fragments))
        return 0

    def tag(self,
        *,
        create: bool = False,
    ) -> int:
        """Validate main's release commit and optionally create its annotated tag."""
        if self.verify():
            return 1
        version = self.current_version()
        name = f"v{version}"
        if self._git("status", "--porcelain"):
            raise ReleaseError("tagging requires a clean working tree")
        if self._git("branch", "--show-current") != "main":
            raise ReleaseError("tagging requires the main branch")
        try:
            origin_main = self._git("rev-parse", "refs/remotes/origin/main")
        except ReleaseError:
            origin_main = None
        if origin_main and self._git("rev-parse", "HEAD") != origin_main:
            raise ReleaseError("HEAD must equal the locally fetched origin/main")
        head_commit = self._git("log", "-1", "--format=%s")
        expected_commit = f"chore(release): {name}"
        if head_commit != expected_commit:
            raise ReleaseError(
                f"expected release commit message: {expected_commit}"
            )
        if version in self.tags():
            raise ReleaseError(f"tag {name} already exists")
        if create:
            self._git("tag", "-a", name, "-m", name)
            print(f"Created annotated tag {name}; no push or publication was performed")
        else:
            print(f"Tag {name} is ready; use tag --create to create it locally")
        return 0

    def tag_release(self,
        create: bool = False,
    ) -> int:
        """Backward-compatibility alias for tag()."""
        return self.tag(create=create)


def main(
    argv: list[str] | None = None,
) -> int:
    """Dispatch the local release commands shared by developers and CI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "status", "verify", "unreleased"):
        sub.add_parser(command)
    check_fragment = sub.add_parser("check-fragment")
    check_fragment.add_argument(
        "--base", default="origin/main", help="git revision to diff against"
    )
    prepare = sub.add_parser("prepare")
    prepare.add_argument("version", nargs="?", default="auto")
    prepare.add_argument("--dry-run", action="store_true")
    new = sub.add_parser("new")
    new.add_argument("--id")
    new.add_argument("-c", "--category", required=True, choices=CATEGORY_ORDER)
    new.add_argument("-m", "--message", required=True)
    notes = sub.add_parser("notes")
    notes.add_argument("version", nargs="?")
    tag = sub.add_parser("tag")
    tag.add_argument("--create", action="store_true")
    args = parser.parse_args(argv)
    repo = ReleaseRepo(args.root)
    try:
        if args.command in ("check", "status"):
            return repo.report(status=args.command == "status")
        if args.command == "prepare":
            return repo.prepare(args.version, dry_run=args.dry_run)
        if args.command == "new":
            return repo.new(args.id, args.category, args.message)
        if args.command == "check-fragment":
            errors, warnings = repo.check_fragment(args.base)
            for warning in warnings:
                print(f"WARNING: {warning}")
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            if not errors:
                print("changelog fragment coverage: OK")
            return 1 if errors else 0
        if args.command == "verify":
            return repo.verify()
        if args.command == "tag":
            return repo.tag(create=args.create)
        if args.command == "notes":
            return repo.notes(args.version)
        if args.command == "unreleased":
            return repo.unreleased()
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
