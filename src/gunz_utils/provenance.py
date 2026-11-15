"""Runtime and execution provenance with explicit environment allowlisting."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import sys
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .benchmark.io import GitInfo, capture_git_info
from .io import atomic_json_write
from .redaction import SECRET_PATTERNS, redact, redact_dict
from .structures import freeze_structure


@dataclass(frozen=True, slots=True)
class RuntimeProvenance:
    """Portable runtime metadata for reproducible artifacts."""

    captured_at: str
    python_version: str
    python_implementation: str
    platform: str
    machine: str
    executable: str
    environment: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze environment metadata for stable provenance snapshots."""
        object.__setattr__(
            self,
            "environment",
            freeze_structure(dict(self.environment)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize runtime provenance to a dictionary."""
        return {
            "captured_at": self.captured_at,
            "python_version": self.python_version,
            "python_implementation": self.python_implementation,
            "platform": self.platform,
            "machine": self.machine,
            "executable": self.executable,
            "environment": dict(self.environment),
        }

    @classmethod
    def from_dict(cls,
        data: Mapping[str, Any],
    ) -> RuntimeProvenance:
        """Deserialize runtime provenance from a dictionary."""
        return cls(
            captured_at=data["captured_at"],
            python_version=data["python_version"],
            python_implementation=data["python_implementation"],
            platform=data["platform"],
            machine=data["machine"],
            executable=data["executable"],
            environment=dict(data.get("environment", {})),
        )


def _redact_environment_value(
    name: str,
    value: str,
) -> str:
    """Redact secret-named values and passwords embedded in URI user-info.

    Parameters
    ----------
    name : str
        name parameter.
    value : str
        value parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    normalized_name = name.casefold()
    if any(pattern in normalized_name for pattern in SECRET_PATTERNS):
        return str(redact(value, show_chars=0))

    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme:
        return value

    sanitized_netloc = parsed.netloc
    if "@" in parsed.netloc:
        userinfo, hostinfo = parsed.netloc.rsplit("@", 1)
        if ":" in userinfo:
            username, _password = userinfo.split(":", 1)
            sanitized_netloc = f"{username}:****@{hostinfo}"
        else:
            sanitized_netloc = f"****@{hostinfo}"

    sanitized_query = parsed.query
    if parsed.query:
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
        new_pairs = []
        for qk, qv in pairs:
            if any(pattern in qk.lower() for pattern in SECRET_PATTERNS):
                new_pairs.append((qk, "****"))
            else:
                new_pairs.append((qk, qv))
        sanitized_query = urlencode(new_pairs)

    sanitized = parsed._replace(netloc=sanitized_netloc, query=sanitized_query)
    return urlunsplit(sanitized)


def capture_runtime_provenance(
    *,
    environment_allowlist: Iterable[str] = (),
) -> RuntimeProvenance:
    """Capture runtime metadata without leaking arbitrary environment values.

    Parameters
    ----------
    environment_allowlist : Iterable[str]
        environment_allowlist parameter.

    Returns
    -------
    RuntimeProvenance
        The result of the operation.
    """
    requested = tuple(environment_allowlist)
    if any(
        not isinstance(name, str) or not name
        for name in requested
    ):
        raise ValueError(
            "environment_allowlist must contain non-empty strings"
        )
    allowed = sorted(set(requested))
    environment = {
        name: _redact_environment_value(name, os.environ[name])
        for name in allowed
        if name in os.environ
    }
    return RuntimeProvenance(
        captured_at=datetime.now(UTC).isoformat(),
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        platform=platform.platform(),
        machine=platform.machine(),
        executable=sys.executable,
        environment=environment,
    )


@dataclass(frozen=True, slots=True)
class ExecutionManifest:
    """Portable provenance record for one execution attempt.

    Attributes
    ----------
    created_at : str
        UTC ISO-8601 creation timestamp.
    run_id : str
        Stable execution identifier.
    runtime : RuntimeProvenance
        Captured interpreter/platform/environment metadata.
    git : GitInfo
        Repository revision metadata.
    parent_run_id : str | None
        Optional parent execution identifier.
    attempt : int
        One-based attempt counter.
    seed : int | None
        Optional caller-defined random seed.
    config : dict[str, Any]
        Caller-supplied configuration snapshot.
    inputs : dict[str, Any]
        Caller-supplied input/data identity metadata.
    packages : dict[str, str]
        Requested installed package versions.
    schema_version : int
        Manifest schema version.
    """

    created_at: str
    run_id: str
    runtime: RuntimeProvenance
    git: GitInfo
    parent_run_id: str | None = None
    attempt: int = 1
    seed: int | None = None
    config: Mapping[str, Any] = field(default_factory=dict)
    inputs: Mapping[str, Any] = field(default_factory=dict)
    packages: Mapping[str, str] = field(default_factory=dict)
    schema_version: int = 1

    def __post_init__(self) -> None:
        """Validate identifiers and freeze nested manifest snapshots."""
        if not isinstance(self.created_at, str) or not self.created_at:
            raise ValueError("created_at must be a non-empty string")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a non-empty string")
        if self.parent_run_id is not None and (
            not isinstance(self.parent_run_id, str)
            or not self.parent_run_id
        ):
            raise ValueError(
                "parent_run_id must be None or a non-empty string"
            )
        if (
            isinstance(self.attempt, bool)
            or not isinstance(self.attempt, int)
            or self.attempt < 1
        ):
            raise ValueError("attempt must be a positive integer")
        if self.seed is not None and (
            isinstance(self.seed, bool)
            or not isinstance(self.seed, int)
        ):
            raise ValueError("seed must be None or an integer")
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version < 1
        ):
            raise ValueError("schema_version must be a positive integer")

        packages = dict(self.packages)
        if any(
            not isinstance(name, str)
            or not name
            or not isinstance(version, str)
            for name, version in packages.items()
        ):
            raise ValueError(
                "packages must map non-empty string names to string versions"
            )

        object.__setattr__(
            self,
            "config",
            freeze_structure(redact_dict(dict(self.config), show_chars=0)),
        )
        object.__setattr__(
            self,
            "inputs",
            freeze_structure(dict(self.inputs)),
        )
        object.__setattr__(
            self,
            "packages",
            freeze_structure(packages),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize execution manifest to a dictionary."""
        return {
            "created_at": self.created_at,
            "run_id": self.run_id,
            "runtime": self.runtime.to_dict(),
            "git": {
                "commit": self.git.commit,
                "branch": self.git.branch,
                "dirty": self.git.dirty,
            },
            "parent_run_id": self.parent_run_id,
            "attempt": self.attempt,
            "seed": self.seed,
            "config": dict(self.config),
            "inputs": dict(self.inputs),
            "packages": dict(self.packages),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls,
        data: Mapping[str, Any],
    ) -> ExecutionManifest:
        """Deserialize execution manifest from a dictionary."""
        git_data = data["git"]
        git_info = GitInfo(
            commit=git_data.get("commit"),
            branch=git_data.get("branch"),
            dirty=git_data.get("dirty"),
        )
        runtime_data = data["runtime"]
        runtime_info = (
            runtime_data
            if isinstance(runtime_data, RuntimeProvenance)
            else RuntimeProvenance.from_dict(runtime_data)
        )
        return cls(
            created_at=data["created_at"],
            run_id=data["run_id"],
            runtime=runtime_info,
            git=git_info,
            parent_run_id=data.get("parent_run_id"),
            attempt=data.get("attempt", 1),
            seed=data.get("seed"),
            config=dict(data.get("config", {})),
            inputs=dict(data.get("inputs", {})),
            packages=dict(data.get("packages", {})),
            schema_version=data.get("schema_version", 1),
        )

    def to_json(self,
        indent: int | None = None,
    ) -> str:
        """Serialize execution manifest to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_json(cls,
        json_str: str,
    ) -> ExecutionManifest:
        """Deserialize execution manifest from a JSON string."""
        return cls.from_dict(json.loads(json_str))



def capture_execution_manifest(
    *,
    config: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
    seed: int | None = None,
    project_root: str | Path = ".",
    parent_run_id: str | None = None,
    attempt: int = 1,
    package_names: tuple[str, ...] = (),
    environment_keys: tuple[str, ...] = (),
    run_id: str | None = None,
) -> ExecutionManifest:
    """Capture a portable execution provenance manifest.

    Parameters
    ----------
    config : dict[str, Any] | None, optional
        Configuration snapshot copied into the manifest.
    inputs : dict[str, Any] | None, optional
        Input/data identity metadata copied into the manifest.
    seed : int | None, optional
        Caller-defined random seed.
    project_root : str | Path, optional
        Repository root used for Git provenance.
    parent_run_id : str | None, optional
        Parent execution identifier.
    attempt : int, optional
        One-based attempt counter. Must be positive.
    package_names : tuple[str, ...], optional
        Installed package distributions whose versions should be recorded.
    environment_keys : tuple[str, ...], optional
        Environment variables explicitly allowed into runtime provenance.
    run_id : str | None, optional
        Explicit run identifier. A UUID4 string is generated when omitted.

    Returns
    -------
    ExecutionManifest
        Captured immutable provenance record.

    Raises
    ------
    ValueError
        If attempt is not positive or run_id is empty.
    """
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    normalized_run_id = None
    if run_id is not None:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        normalized_run_id = run_id.strip()

    normalized_parent_run_id = None
    if parent_run_id is not None:
        if (
            not isinstance(parent_run_id, str)
            or not parent_run_id.strip()
        ):
            raise ValueError(
                "parent_run_id must be None or a non-empty string"
            )
        normalized_parent_run_id = parent_run_id.strip()

    runtime = capture_runtime_provenance(
        environment_allowlist=environment_keys,
    )
    if any(
        not isinstance(name, str) or not name
        for name in package_names
    ):
        raise ValueError(
            "package_names must contain non-empty strings"
        )

    packages: dict[str, str] = {}
    for name in dict.fromkeys(package_names):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue

    return ExecutionManifest(
        created_at=runtime.captured_at,
        run_id=normalized_run_id or str(uuid.uuid4()),
        runtime=runtime,
        git=capture_git_info(str(Path(project_root).resolve())),
        parent_run_id=normalized_parent_run_id,
        attempt=attempt,
        seed=seed,
        config=config or {},
        inputs=inputs or {},
        packages=packages,
    )


def write_execution_manifest(
    manifest: ExecutionManifest,
    path: str | Path,
    *,
    durable: bool = False,
) -> Path:
    """Atomically persist an execution manifest as deterministic JSON.

    Parameters
    ----------
    manifest : ExecutionManifest
        manifest parameter.
    path : str | Path
        path parameter.
    durable : bool
        durable parameter.

    Returns
    -------
    Path
        The result of the operation.
    """
    target = Path(path)
    atomic_json_write(
        target,
        manifest,
        pretty=True,
        mkdir=True,
        durable=durable,
    )
    return target


__all__ = [
    "ExecutionManifest",
    "RuntimeProvenance",
    "capture_execution_manifest",
    "capture_runtime_provenance",
    "write_execution_manifest",
]
