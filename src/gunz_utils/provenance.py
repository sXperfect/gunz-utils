"""Runtime provenance capture with explicit environment allowlisting."""

from __future__ import annotations

import os
import platform
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class RuntimeProvenance:
    """Portable runtime metadata for reproducible artifacts."""

    captured_at: str
    python_version: str
    python_implementation: str
    platform: str
    machine: str
    executable: str
    environment: dict[str, str] = field(default_factory=dict)


def capture_runtime_provenance(
    *,
    environment_allowlist: Iterable[str] = (),
) -> RuntimeProvenance:
    """Capture runtime metadata without leaking arbitrary environment values."""
    allowed = sorted(set(environment_allowlist))
    environment = {name: os.environ[name] for name in allowed if name in os.environ}
    return RuntimeProvenance(
        captured_at=datetime.now(timezone.utc).isoformat(),
        python_version=platform.python_version(),
        python_implementation=platform.python_implementation(),
        platform=platform.platform(),
        machine=platform.machine(),
        executable=sys.executable,
        environment=environment,
    )


__all__ = ["RuntimeProvenance", "capture_runtime_provenance"]
