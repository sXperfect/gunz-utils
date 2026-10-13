"""Perpetual security audit phase 36 (round 4, deepest).

Re-audit of ``config``, ``fs``, ``subprocess``, ``structures``, and
``result``.

Findings (all NEW, not fixed in phases 1-35):

1. ``config.env_overrides`` never verifies that an environment key actually
   begins with the configured ``prefix`` (config.py:73-89).  It slices off
   ``len(prefix_upper)`` characters unconditionally and then only checks that
   the remainder starts with the separator.  A key that does *not* start with
   the prefix but whose prefix-length prefix is immediately followed by the
   separator is therefore wrongly treated as an override.  For example with
   ``prefix="APP"`` the unrelated key ``XAP_PORT`` is parsed into
   ``{"port": "8080"}`` (and ``ZAP_TOKEN`` into ``{"token": ...}``), injecting
   environment variables owned by other applications into this config.  The
   same holds for any separator (``__``, ``::``, ...).  Correct behavior: the
   uppercased key must start with the uppercased prefix before any slicing.

2. ``subprocess.run_command`` (synchronous, unbounded-output path) leaks an
   untyped ``OverflowError`` for a large-but-finite ``timeout``
   (subprocess.py:422-443).  ``_validate_timeout_value`` accepts any finite
   non-negative number, so a caller-supplied ``timeout`` of e.g. ``1e9``
   (``1e12``, ``1e308``) passes validation, but the internal
   ``subprocess.run(timeout=...)`` cannot represent it and raises
   ``OverflowError`` ("timeout is too large" / "timestamp too large to convert
   to C _PyTime_t") instead of the documented validation error.  The repo
   already bounds socket timeouts (``network._MAX_SOCKET_TIMEOUT``) and
   converts OverflowError to ValueError for ``network``/``upstream_protocol``;
   ``subprocess`` must do the same so a pathological timeout surfaces as a
   clean ``ValueError``.

The remaining GREEN coverage pins correct behavior so the fixes cannot
regress: env_overrides correctly parses real prefixed keys and rejects
colliding paths; run_command accepts normal timeouts and rejects
non-finite/bool timeouts; contained_path rejects symlink escapes; deep_diff
handles cycles and missing-vs-None; result variant typing holds.
"""

import sys

import pytest

from gunz_utils.config import env_overrides
from gunz_utils.fs import contained_path, lexical_contained_path
from gunz_utils.result import Result
from gunz_utils.structures import deep_diff
from gunz_utils.subprocess import run_command

# ---------------------------------------------------------------------------
# Finding 1: env_overrides must require the key to actually start with prefix
# ---------------------------------------------------------------------------


def test_env_overrides_ignores_non_prefixed_keys():
    """RED: keys that do not start with the prefix (but whose prefix-length
    slice is followed by the separator) must be ignored.  ``XAP_PORT`` does not
    start with ``APP``, yet it is currently parsed into ``{"port": "8080"}``.
    """
    assert env_overrides({"XAP_PORT": "8080"}, prefix="APP") == {}
    assert env_overrides({"ZAP_TOKEN": "t"}, prefix="APP") == {}


def test_env_overrides_ignores_non_prefixed_keys_non_underscore_separator():
    """RED: the same prefix-boundary requirement must hold for a non-underscore
    separator such as ``::``.
    """
    assert env_overrides({"XAP::PORT": "9"}, prefix="APP", separator="::") == {}


# ---------------------------------------------------------------------------
# Finding 2: run_command must not leak OverflowError for oversized timeouts
# ---------------------------------------------------------------------------


def test_run_command_rejects_oversized_finite_timeout():
    """RED: a large-but-finite timeout currently surfaces as OverflowError from
    ``subprocess.run``.  It must instead be rejected as a clean ``ValueError``
    (the timeout is validated as a finite non-negative number but cannot be
    represented by the underlying subprocess machinery).
    """
    with pytest.raises(ValueError):
        run_command([sys.executable, "-c", "pass"], timeout=1e12)


def test_run_command_rejects_very_large_finite_timeout():
    """RED: the same holds for an extreme finite timeout such as ``1e308``."""
    with pytest.raises(ValueError):
        run_command([sys.executable, "-c", "pass"], timeout=1e308)


# ---------------------------------------------------------------------------
# GREEN: config behavior that must not regress
# ---------------------------------------------------------------------------


def test_env_overrides_parses_real_prefixed_keys():
    """GREEN: keys that genuinely begin with the prefix are parsed."""
    assert env_overrides(
        {"APP_HOST": "h1", "APP_PORT": "80"}, prefix="APP"
    ) == {"host": "h1", "port": "80"}
    assert env_overrides(
        {"APP::HOST": "h2"}, prefix="APP", separator="::"
    ) == {"host": "h2"}


def test_env_overrides_nests_and_detects_conflicts():
    """GREEN: nested paths are built and colliding paths raise ValueError."""
    assert env_overrides(
        {"APP_DB__HOST": "h", "APP_DB__PORT": "1"}, prefix="APP"
    ) == {"db": {"host": "h", "port": "1"}}
    with pytest.raises(ValueError):
        env_overrides({"APP_PORT": "1", "app_port": "2"}, prefix="APP")


# ---------------------------------------------------------------------------
# GREEN: subprocess behavior that must not regress
# ---------------------------------------------------------------------------


def test_run_command_accepts_normal_timeout():
    """GREEN: an ordinary finite timeout is accepted and the command runs."""
    result = run_command([sys.executable, "-c", "pass"], timeout=30.0)
    assert result.returncode == 0


def test_run_command_rejects_non_finite_and_bool_timeouts():
    """GREEN: non-finite and boolean timeouts are rejected with ValueError."""
    for bad in (float("nan"), float("inf"), float("-inf"), True):
        with pytest.raises(ValueError):
            run_command([sys.executable, "-c", "pass"], timeout=bad)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: fs containment that must not regress
# ---------------------------------------------------------------------------


def test_contained_path_rejects_symlink_escape(tmp_path):
    """GREEN: a symlink inside root pointing outside must be rejected."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("x")
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        contained_path(root, "link/secret")
    with pytest.raises(ValueError):
        lexical_contained_path(root, "link/secret")


def test_contained_path_allows_internal_path(tmp_path):
    """GREEN: a normal path inside root is returned resolved and contained."""
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    assert contained_path(root, "sub") == (root / "sub").resolve()
    assert lexical_contained_path(root, "sub") == (root / "sub")


# ---------------------------------------------------------------------------
# GREEN: structures behavior that must not regress
# ---------------------------------------------------------------------------


def test_deep_diff_cycle_safety_and_missing_vs_none():
    """GREEN: deep_diff terminates on cycles and distinguishes missing from
    None.
    """
    a = {"k": 1}
    a["self"] = a
    b = {"k": 1}
    b["self"] = b
    assert deep_diff(a, b) == []
    missing = deep_diff({"a": None}, {})
    assert missing[0].kind == "missing_right"
    assert deep_diff({"a": None}, {"a": 1})[0].kind == "value"


# ---------------------------------------------------------------------------
# GREEN: result behavior that must not regress
# ---------------------------------------------------------------------------


def test_result_variant_typing_and_mapping():
    """GREEN: Result infers variants, maps, and maps errors correctly."""
    assert Result.ok(1).is_ok is True
    assert Result.err("e").is_err is True
    assert Result.ok(0).map(lambda x: x + 1).unwrap() == 1
    assert Result.err("e").unwrap_or(5) == 5
    assert Result.ok("x").map_error(lambda e: e.upper()).unwrap() == "x"
    with pytest.raises(RuntimeError):
        Result.err("e").unwrap()
