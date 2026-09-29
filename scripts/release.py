#!/usr/bin/env python3
"""Deterministic local release and changelog tooling for gunz-utils.

This module is intentionally standard-library only.  It is the canonical place
for release metadata checks and release preparation; GitHub Actions only calls
into it and does not contain independent versioning logic.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
VERSION_LITERAL_RE = re.compile(
    r'^\s*__version__\s*=\s*["\']\d+\.\d+\.\d+["\']\s*$',
    re.MULTILINE,
)
CHANGELOG_HEADING_RE = re.compile(
    r"^## \[(?P<version>[^]]+)\](?:\s+—\s+.+)?$",
    re.MULTILINE,
)
UNRELEASED_SECTION_RE = re.compile(
    r"^## \[Unreleased\]\s*\n(?P<body>.*?)(?=^## \[|\Z)",
    re.MULTILINE | re.DOTALL,
)

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
BUMP_RANK = {"none": 0, "patch": 1, "minor": 2, "major": 3}
CATEGORY_BUMP = {
    "breaking": "major",
    "removed": "major",
    "added": "minor",
    "changed": "minor",
    "deprecated": "minor",
    "security": "patch",
    "fixed": "patch",
    "performance": "patch",
    "docs": "patch",
    "internal": "patch",
}
UNRELEASED_NOTE = (
    "Unreleased changes are collected as conflict-free fragments in "
    "`changes/`. Run `python scripts/release.py status` to inspect them."
)


class ReleaseError(RuntimeError):
    """Raised for invalid release metadata or an unsafe release operation."""


@dataclass(frozen=True, order=True)
class SemVer:
    """A strict MAJOR.MINOR.PATCH semantic version."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> SemVer:
        match = SEMVER_RE.fullmatch(value.strip())
        if match is None:
            raise ReleaseError(
                f"invalid version {value!r}; expected strict MAJOR.MINOR.PATCH"
            )
        return cls(*(int(group) for group in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class Fragment:
    """One changelog fragment."""

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


class ReleaseRepo:
    """Release operations rooted at one repository checkout."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.pyproject = self.root / "pyproject.toml"
        self.changelog = self.root / "CHANGELOG.md"
        self.fragments_dir = self.root / "changes"
        self.source_dir = self.root / "src" / "gunz_utils"
        self.init_py = self.source_dir / "__init__.py"
        self.version_module = self.source_dir / "_version.py"
        self.sphinx_conf = self.root / "docs" / "source" / "conf.py"

    def current_version(self) -> SemVer:
        with self.pyproject.open("rb") as handle:
            data = tomllib.load(handle)
        value = data.get("project", {}).get("version")
        if not isinstance(value, str):
            raise ReleaseError("pyproject.toml [project].version is missing")
        return SemVer.parse(value)

    def fragments(self) -> list[Fragment]:
        if not self.fragments_dir.is_dir():
            raise ReleaseError("missing changes/ fragment directory")
        fragments: list[Fragment] = []
        seen_ids: set[str] = set()
        for path in sorted(self.fragments_dir.glob("*.md")):
            if path.name == "README.md":
                continue
            stem = path.name[:-3]
            if "." not in stem:
                raise ReleaseError(
                    f"invalid fragment filename {path.name!r}; "
                    "expected <id>.<category>.md"
                )
            identifier, category = stem.rsplit(".", 1)
            valid_identifier = re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9._-]*", identifier
            )
            if not identifier or valid_identifier is None:
                raise ReleaseError(f"invalid fragment id in {path.name!r}")
            if category not in CATEGORY_TITLES:
                allowed = ", ".join(CATEGORY_ORDER)
                raise ReleaseError(
                    f"invalid fragment category {category!r} in {path.name}; "
                    f"allowed: {allowed}"
                )
            if identifier in seen_ids:
                raise ReleaseError(f"duplicate fragment id {identifier!r}")
            seen_ids.add(identifier)
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                raise ReleaseError(f"empty changelog fragment: {path.name}")
            fragments.append(Fragment(identifier, category, text, path))
        return fragments

    @staticmethod
    def required_bump(fragments: Iterable[Fragment]) -> str:
        required = "none"
        for fragment in fragments:
            candidate = CATEGORY_BUMP[fragment.category]
            if BUMP_RANK[candidate] > BUMP_RANK[required]:
                required = candidate
        return required

    @staticmethod
    def target_satisfies(current: SemVer, target: SemVer, bump: str) -> bool:
        if target <= current:
            return False
        if bump == "major":
            return target.major > current.major
        if bump == "minor":
            return target.major > current.major or (
                target.major == current.major and target.minor > current.minor
            )
        if bump == "patch":
            return True
        return target > current

    @staticmethod
    def minimum_target(current: SemVer, bump: str) -> SemVer:
        if bump == "major":
            return SemVer(current.major + 1, 0, 0)
        if bump == "minor":
            return SemVer(current.major, current.minor + 1, 0)
        return SemVer(current.major, current.minor, current.patch + 1)

    def _git_tags(self) -> list[SemVer]:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), "tag", "--list", "v*"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if result.returncode != 0:
            return []
        tags: list[SemVer] = []
        for line in result.stdout.splitlines():
            value = line.strip()
            if not value.startswith("v"):
                continue
            try:
                tags.append(SemVer.parse(value[1:]))
            except ReleaseError:
                continue
        return sorted(set(tags))

    def check(self) -> CheckResult:
        errors: list[str] = []
        warnings: list[str] = []

        try:
            current = self.current_version()
        except (OSError, tomllib.TOMLDecodeError, ReleaseError) as exc:
            return CheckResult((str(exc),), ())

        try:
            fragments = self.fragments()
        except (OSError, ReleaseError) as exc:
            errors.append(str(exc))
            fragments = []

        for frag in fragments:
            for marker in ("<<<<<<<", "=======", ">>>>>>>"):
                if marker in frag.text:
                    errors.append(
                        f"changelog fragment {frag.path.name} contains unresolved git conflict marker {marker!r}"
                    )
            if frag.text.startswith("* "):
                warnings.append(
                    f"changelog fragment {frag.path.name} uses '*' bullet; standard format prefers '- '"
                )

        if not self.changelog.is_file():
            errors.append("missing CHANGELOG.md")
            changelog_text = ""
        else:
            changelog_text = self.changelog.read_text(encoding="utf-8")
            if UNRELEASED_SECTION_RE.search(changelog_text) is None:
                errors.append(
                    "CHANGELOG.md must contain a top-level [Unreleased] section"
                )

            seen: set[str] = set()
            for match in CHANGELOG_HEADING_RE.finditer(changelog_text):
                value = match.group("version")
                if value == "Unreleased":
                    continue
                try:
                    SemVer.parse(value)
                except ReleaseError:
                    errors.append(f"invalid changelog version heading: {value!r}")
                    continue
                if value in seen:
                    errors.append(f"duplicate changelog version heading: {value}")
                seen.add(value)

        if self.source_dir.is_dir():
            for path in sorted(self.source_dir.rglob("*.py")):
                if path == self.init_py:
                    continue
                text = path.read_text(encoding="utf-8")
                if VERSION_LITERAL_RE.search(text):
                    errors.append(
                        f"{path.relative_to(self.root)} contains a package "
                        "__version__ literal"
                    )

        if not self.version_module.is_file():
            errors.append("missing src/gunz_utils/_version.py")
        else:
            version_text = self.version_module.read_text(encoding="utf-8")
            if 'metadata.version("gunz-utils")' not in version_text:
                errors.append(
                    "gunz_utils._version must derive from importlib.metadata"
                )

        if self.init_py.is_file():
            init_text = self.init_py.read_text(encoding="utf-8")
            if (
                "from ._version import __version__" not in init_text
                or "__version__ = _resolve_package_version()" not in init_text
            ):
                errors.append(
                    "gunz_utils.__version__ must use the shared version resolver"
                )
            if VERSION_LITERAL_RE.search(init_text):
                errors.append(
                    "src/gunz_utils/__init__.py contains a static version literal"
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
            if 'package_version("gunz-utils")' not in conf_text:
                errors.append(
                    "Sphinx release must derive from installed package metadata"
                )

        tags = self._git_tags()
        if tags:
            latest = tags[-1]
            if latest > current:
                errors.append(
                    f"latest tag v{latest} is newer than pyproject version {current}"
                )
            elif current not in tags:
                warnings.append(
                    f"pyproject version {current} has no matching tag; latest tag is "
                    f"v{latest}"
                )
        else:
            warnings.append("Git tags are unavailable in this checkout")

        required = self.required_bump(fragments)
        if required != "none":
            minimum = self.minimum_target(current, required)
            warnings.append(
                f"current fragments require at least a {required} release "
                f"(minimum {minimum})"
            )

        return CheckResult(tuple(errors), tuple(warnings))

    def status(self) -> int:
        current = self.current_version()
        fragments = self.fragments()
        tags = self._git_tags()
        counts = Counter(fragment.category for fragment in fragments)
        required = self.required_bump(fragments)

        print(f"Current version:       {current}")
        if tags:
            print(f"Latest Git tag:        v{tags[-1]}")
        else:
            print("Latest Git tag:        unavailable")
        print(f"Unreleased fragments:  {len(fragments)}")
        for category in CATEGORY_ORDER:
            if counts[category]:
                print(f"  {category:<12} {counts[category]}")
        if required == "none":
            print("Minimum SemVer bump:   none")
        else:
            print(
                f"Minimum SemVer bump:   {required} "
                f"(>= {self.minimum_target(current, required)})"
            )

        result = self.check()
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 0 if result.ok else 1

    def check_command(self) -> int:
        result = self.check()
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        if result.ok:
            print("release metadata check: OK")
            return 0
        return 1

    @staticmethod
    def _render_fragment_text(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("- "):
            return stripped
        lines = stripped.splitlines()
        return "- " + lines[0] + "".join(f"\n  {line}" for line in lines[1:])

    def _render_release_sections(self, fragments: list[Fragment]) -> str:
        grouped: dict[str, list[Fragment]] = defaultdict(list)
        for fragment in fragments:
            grouped[fragment.category].append(fragment)

        parts: list[str] = []
        for category in CATEGORY_ORDER:
            if category == "internal" or not grouped[category]:
                continue
            parts.append(f"### {CATEGORY_TITLES[category]}")
            entries = [
                self._render_fragment_text(fragment.text)
                for fragment in grouped[category]
            ]
            parts.append("\n\n".join(entries))
        if not parts:
            parts.extend(
                [
                    "### Internal",
                    "- Internal-only maintenance; no user-facing changelog entries.",
                ]
            )
        return "\n\n".join(parts)

    def _updated_pyproject(self, target: SemVer) -> str:
        text = self.pyproject.read_text(encoding="utf-8")
        project_match = re.search(r"^\[project\]\s*$", text, re.MULTILINE)
        if project_match is None:
            raise ReleaseError("pyproject.toml is missing [project]")
        next_section = re.search(
            r"^\[[^]]+\]\s*$",
            text[project_match.end() :],
            re.MULTILINE,
        )
        end = (
            project_match.end() + next_section.start()
            if next_section is not None
            else len(text)
        )
        section = text[project_match.end() : end]
        replaced, count = re.subn(
            r'(?m)^version[ \t]*=[ \t]*"[^"]+"[ \t]*$',
            f'version = "{target}"',
            section,
            count=1,
        )
        if count != 1:
            raise ReleaseError("could not replace [project].version")
        return text[: project_match.end()] + replaced + text[end:]

    def _updated_changelog(
        self,
        target: SemVer,
        fragments: list[Fragment],
        release_date: dt.date,
    ) -> str:
        text = self.changelog.read_text(encoding="utf-8")
        if re.search(
            rf"^## \[{re.escape(str(target))}\](?:\s|$)",
            text,
            re.MULTILINE,
        ):
            raise ReleaseError(f"CHANGELOG.md already contains [{target}]")
        match = UNRELEASED_SECTION_RE.search(text)
        if match is None:
            raise ReleaseError("CHANGELOG.md is missing [Unreleased]")
        release_body = self._render_release_sections(fragments)
        replacement = (
            "## [Unreleased]\n\n"
            f"{UNRELEASED_NOTE}\n\n"
            f"## [{target}] — {release_date.isoformat()}\n\n"
            f"{release_body}\n\n"
        )
        return text[: match.start()] + replacement + text[match.end() :]

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        tmp = path.with_name(path.name + ".release-tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)

    def prepare(self, target_text: str = "auto", *, dry_run: bool = False) -> int:
        result = self.check()
        if not result.ok:
            for error in result.errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1

        current = self.current_version()
        fragments = self.fragments()
        if not fragments:
            raise ReleaseError("no changelog fragments to release")

        required = self.required_bump(fragments)
        effective_bump = "patch" if required == "none" else required

        if target_text.strip().lower() == "auto":
            target = self.minimum_target(current, effective_bump)
        else:
            target = SemVer.parse(target_text)
            if not self.target_satisfies(current, target, required):
                minimum = self.minimum_target(current, required)
                raise ReleaseError(
                    f"{target} is too small for {required} changes; "
                    f"minimum allowed target is {minimum}"
                )

        pyproject_text = self._updated_pyproject(target)
        changelog_text = self._updated_changelog(target, fragments, dt.date.today())

        if dry_run:
            print(f"[DRY-RUN] Target version: {target} (bump: {required})")
            print(f"[DRY-RUN] Fragments consumed ({len(fragments)}):")
            for frag in fragments:
                print(f"  - {frag.path.name}")
            print("\n[DRY-RUN] Proposed CHANGELOG.md addition:")
            print("-" * 60)
            release_body = self._render_release_sections(fragments)
            print(f"## [{target}] — {dt.date.today().isoformat()}\n\n{release_body}")
            print("-" * 60)
            print(f"[DRY-RUN] No files modified and no fragments deleted.")
            return 0

        self._atomic_write(self.pyproject, pyproject_text)
        self._atomic_write(self.changelog, changelog_text)
        for fragment in fragments:
            fragment.path.unlink()

        print(f"Prepared release {target}.")
        print(f"Recommended commit: chore(release): v{target}")
        print(
            f"After merge and verification, create tag v{target} and a matching "
            "GitHub Release."
        )
        return 0

    def verify(self) -> int:
        result = self.check()
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        if not result.ok:
            return 1

        current = self.current_version()
        fragments = self.fragments()
        if fragments:
            print(
                f"ERROR: {len(fragments)} changelog fragment(s) remain; "
                "run prepare before release verification",
                file=sys.stderr,
            )
            return 1
        text = self.changelog.read_text(encoding="utf-8")
        release_heading = re.search(
            rf"^## \[{re.escape(str(current))}\](?:\s|$)",
            text,
            re.MULTILINE,
        )
        if release_heading is None:
            print(
                f"ERROR: CHANGELOG.md has no [{current}] release entry",
                file=sys.stderr,
            )
            return 1
        print(f"release {current} is ready for commit/tag verification")
        print(f"expected commit message: chore(release): v{current}")
        print(f"expected tag: v{current}")
        return 0

    def unreleased(self) -> int:
        fragments = self.fragments()
        if not fragments:
            print("No unreleased fragments in changes/.")
            return 0
        sections = self._render_release_sections(fragments)
        print(sections)
        return 0

    def notes(self, version_text: str | None = None) -> int:
        if version_text is None:
            target = self.current_version()
        else:
            target = SemVer.parse(version_text)

        if not self.changelog.is_file():
            print("ERROR: missing CHANGELOG.md", file=sys.stderr)
            return 1

        text = self.changelog.read_text(encoding="utf-8")
        heading_pattern = rf"^## \[{re.escape(str(target))}\](?:\s+—\s+.+)?$"
        match = re.search(heading_pattern, text, re.MULTILINE)
        if match is None:
            print(
                f"ERROR: release section [{target}] not found in CHANGELOG.md",
                file=sys.stderr,
            )
            return 1

        body_start = match.end()
        next_match = re.search(r"^## \[", text[body_start:], re.MULTILINE)
        if next_match is not None:
            notes_text = text[body_start : body_start + next_match.start()].strip()
        else:
            notes_text = text[body_start:].strip()

        print(notes_text)
        return 0

    def new_fragment(
        self,
        category: str,
        message: str,
        identifier: str | None = None,
    ) -> int:
        category = category.lower().strip()
        if category not in CATEGORY_TITLES:
            allowed = ", ".join(CATEGORY_ORDER)
            print(
                f"ERROR: invalid category {category!r}; allowed: {allowed}",
                file=sys.stderr,
            )
            return 1

        msg = message.strip()
        if not msg:
            print("ERROR: fragment message cannot be empty", file=sys.stderr)
            return 1

        if not identifier:
            slug = re.sub(r"[^a-z0-9]+", "-", msg.lower()).strip("-")[:35]
            date_str = dt.date.today().strftime("%Y%m%d")
            identifier = f"{date_str}-{slug}" if slug else f"{date_str}-change"

        valid_identifier = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", identifier)
        if valid_identifier is None:
            print(f"ERROR: invalid fragment id {identifier!r}", file=sys.stderr)
            return 1

        filename = f"{identifier}.{category}.md"
        path = self.fragments_dir / filename
        if path.exists():
            print(f"ERROR: fragment {filename} already exists", file=sys.stderr)
            return 1

        formatted_message = self._render_fragment_text(msg) + "\n"
        self.fragments_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(formatted_message, encoding="utf-8")
        print(f"Created fragment: {path.relative_to(self.root)}")
        return 0

    def tag_release(self, create: bool = False) -> int:
        current = self.current_version()
        tag_name = f"v{current}"

        verify_status = self.verify()
        if verify_status != 0:
            return verify_status

        status_proc = subprocess.run(
            ["git", "-C", str(self.root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        if status_proc.returncode != 0:
            print("ERROR: git status failed", file=sys.stderr)
            return 1
        if status_proc.stdout.strip():
            print("ERROR: working tree contains uncommitted changes:", file=sys.stderr)
            for line in status_proc.stdout.splitlines():
                print(f"  {line}", file=sys.stderr)
            return 1

        branch_proc = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        branch = branch_proc.stdout.strip()
        if branch != "main":
            print(
                f"WARNING: current branch is {branch!r}; releases should normally be tagged on 'main'",
                file=sys.stderr,
            )

        log_proc = subprocess.run(
            ["git", "-C", str(self.root), "log", "-1", "--format=%s"],
            capture_output=True,
            text=True,
            check=False,
        )
        head_commit = log_proc.stdout.strip()
        expected_commit = f"chore(release): {tag_name}"
        if head_commit != expected_commit:
            print(
                f"ERROR: HEAD commit message is {head_commit!r}; expected {expected_commit!r}",
                file=sys.stderr,
            )
            return 1

        tags = self._git_tags()
        if current in tags:
            print(
                f"ERROR: tag {tag_name} already exists in repository",
                file=sys.stderr,
            )
            return 1

        if create:
            tag_proc = subprocess.run(
                ["git", "-C", str(self.root), "tag", "-a", tag_name, "-m", tag_name],
                check=False,
                capture_output=True,
                text=True,
            )
            if tag_proc.returncode != 0:
                print(
                    f"ERROR: failed to create tag: {tag_proc.stderr}",
                    file=sys.stderr,
                )
                return tag_proc.returncode
            print(f"Created annotated tag: {tag_name}")
            print(f"Push with: git push origin {tag_name}")
            return 0
        else:
            print(f"Tag {tag_name} is valid and ready to be created.")
            print(f"Run: git tag -a {tag_name} -m \"{tag_name}\"")
            print(f"Or rerun with --create: python scripts/release.py tag --create")
            return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show version, tags, fragments and minimum bump")
    sub.add_parser("check", help="validate release metadata without modifying files")
    sub.add_parser("unreleased", help="render pending fragments in changelog format")

    notes = sub.add_parser(
        "notes",
        help="extract release notes for a version from CHANGELOG.md",
    )
    notes.add_argument(
        "version",
        nargs="?",
        default=None,
        help="target version (default: current version in pyproject.toml)",
    )

    new = sub.add_parser("new", help="create a new changelog fragment file")
    new.add_argument(
        "-c",
        "--category",
        required=True,
        choices=CATEGORY_ORDER,
        help="change category",
    )
    new.add_argument("-m", "--message", required=True, help="description of the change")
    new.add_argument(
        "--id",
        default=None,
        help="optional unique fragment ID (default: date + slug)",
    )

    prepare = sub.add_parser("prepare", help="prepare a release in the working tree")
    prepare.add_argument(
        "version",
        nargs="?",
        default="auto",
        help="target MAJOR.MINOR.PATCH version or 'auto' (default: auto)",
    )
    prepare.add_argument(
        "--dry-run",
        action="store_true",
        help="preview changes without modifying files or deleting fragments",
    )

    sub.add_parser("verify", help="verify a prepared release before tagging")

    tag = sub.add_parser(
        "tag",
        help="validate release commit and optionally create git tag",
    )
    tag.add_argument(
        "--create",
        action="store_true",
        help="create the annotated git tag",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = ReleaseRepo(Path(__file__).resolve().parent.parent)
    try:
        if args.command == "status":
            return repo.status()
        if args.command == "check":
            return repo.check_command()
        if args.command == "unreleased":
            return repo.unreleased()
        if args.command == "notes":
            return repo.notes(args.version)
        if args.command == "new":
            return repo.new_fragment(args.category, args.message, args.id)
        if args.command == "prepare":
            return repo.prepare(args.version, dry_run=args.dry_run)
        if args.command == "verify":
            return repo.verify()
        if args.command == "tag":
            return repo.tag_release(create=args.create)
    except (OSError, tomllib.TOMLDecodeError, ReleaseError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command: {args.command}")



if __name__ == "__main__":
    raise SystemExit(main())
