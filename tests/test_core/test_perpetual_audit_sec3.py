"""Perpetual security & concurrency audit - PHASE 3 regression tests.

Each test exposes a concrete security, secret-redaction, or resource-bound defect
in the audited modules (provenance, provenance_graph, content_store, security,
leases). Tests are written to FAIL ("red") against the current source and must
pass only after the corresponding production fix lands. Production code is
intentionally not modified.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.provenance import (
    _redact_environment_value,
    capture_runtime_provenance,
)


# -----------------------------------------------------------------------------
# provenance.py - allowlisted environment values with embedded credentials leak
# -----------------------------------------------------------------------------


def test_redact_environment_value_masks_query_string_credentials() -> None:
    """Allowlisted values that are URIs must not leak credentials in the query.

    ``_redact_environment_value`` (provenance.py:73-87) only masks passwords
    embedded in the URI *user-info* component. A signed/tokenized URI such as
    ``https://host/export?token=...`` has its credentials in the query string,
    which urlsplit leaves in the ``query`` part; the function returns the value
    unchanged, so the secret is persisted verbatim into the provenance record.
    """
    redacted = _redact_environment_value(
        "SIGNED_URL",
        "https://host/export?token=supersecret-token",
    )
    assert "supersecret-token" not in redacted


def test_redact_environment_value_masks_password_query_parameter() -> None:
    """``?password=...`` query parameters must also be masked."""
    redacted = _redact_environment_value(
        "URL",
        "https://host/path?password=hunter2-secret",
    )
    assert "hunter2-secret" not in redacted


def test_redact_environment_value_masks_key_value_dsn_password() -> None:
    """Credentials in non-URI ``key=value`` DSNs must not leak.

    Common connection strings such as the libpq form
    ``host=db user=admin password=...`` are not URIs, so urlsplit yields no
    netloc with user-info and the function returns the value unchanged,
    persisting the embedded ``password=`` secret into the provenance record.
    """
    redacted = _redact_environment_value(
        "DB_CONN",
        "host=db user=admin password=supersecret password2=also-secret",
    )
    assert "supersecret" not in redacted
    assert "also-secret" not in redacted


def test_capture_runtime_provenance_does_not_leak_allowlisted_dsn_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: an allowlisted DSN with an embedded password must be redacted
    before it is recorded in runtime provenance."""
    monkeypatch.setenv(
        "DATABASE_CONN",
        "host=db user=admin password=dsn-super-secret",
    )
    runtime = capture_runtime_provenance(
        environment_allowlist=("DATABASE_CONN",),
    )
    recorded = runtime.environment["DATABASE_CONN"]
    assert "dsn-super-secret" not in recorded


def test_redact_environment_value_still_masks_uri_userinfo() -> None:
    """Sanity: the existing URI user-info masking remains intact."""
    redacted = _redact_environment_value(
        "DATABASE_URL",
        "postgres://admin:secretpw@localhost:5432/db",
    )
    assert "secretpw" not in redacted
    assert redacted == "postgres://admin:****@localhost:5432/db"


# -----------------------------------------------------------------------------
# content_store.py - put() blocks indefinitely on FIFO / special-file sources
# -----------------------------------------------------------------------------


def test_content_store_put_rejects_fifo_source_without_hanging(
    tmp_path: Path,
) -> None:
    """``ContentAddressedStore.put`` must not block forever on a non-regular
    source.

    ``put`` (content_store.py:696-704) opens the source with ``O_RDONLY`` only
    (no ``O_NONBLOCK``) and only checks ``S_ISREG`` *after* a blocking open. On
    a FIFO, ``os.open(path, O_RDONLY)`` blocks until a writer appears, so the
    regular-file rejection is never reached and the call hangs indefinitely.
    The store must reject a FIFO/special source promptly (e.g. with a non-block
    open and an explicit non-regular-file error).
    """
    probe = (
        "import os, sys, tempfile\n"
        "from gunz_utils.content_store import ContentAddressedStore\n"
        "d = tempfile.mkdtemp()\n"
        "fifo = os.path.join(d, 'src.fifo')\n"
        "os.mkfifo(fifo)\n"
        "store = ContentAddressedStore(os.path.join(d, 'store'))\n"
        "try:\n"
        "    store.put(fifo)\n"
        "except Exception as exc:\n"
        "    print('REJECTED:', type(exc).__name__)\n"
        "else:\n"
        "    print('RETURNED')\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(__file__).resolve().parents[2] / "src"), env.get("PYTHONPATH", "")]
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("ContentAddressedStore.put blocked indefinitely on a FIFO source")

    # Prompt termination (success OR rejection) is the contract; a hang is not.
    assert "REJECTED" in completed.stdout or "RETURNED" in completed.stdout
