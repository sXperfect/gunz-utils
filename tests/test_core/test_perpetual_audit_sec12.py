"""Perpetual security & concurrency audit - PHASE 12 (round-2) regression tests.

Round-2 re-audit of config, env, content_store, provenance, formatting, and
typed_config. Tests are written to FAIL ("red") against the current source (base
463572b, which already contains the phase 1-11 fixes) and must pass only after
the corresponding production fix lands. Production code is intentionally not
modified.

Findings covered here (NEW, not previously flagged):
1. ``env_overrides`` (config.py:67-72) computes the prefix slice against a
   single trailing underscore, but the default separator is ``"__"``. For the
   canonical ``MYAPP__DB__HOST`` key the slice ``name[len(prefix_value):]``
   leaves the second separator underscore attached to the suffix, so the
   ``split(separator)`` produces a leading-underscore segment
   (``{'_db': {'host': ...}}``) instead of the nested ``{'db': {'host': ...}}``.
2. ``env`` (env.py:47) returns a caller-supplied ``default`` without applying
   the module's finiteness guard. The cast path rejects non-finite floats
   (env.py:57-60), but a non-finite float ``default`` (``inf``/``-inf``/``nan``)
   is returned verbatim, bypassing the package finiteness convention.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.config import env_overrides
from gunz_utils.env import env

# -----------------------------------------------------------------------------
# config.py - env_overrides default "__" separator mangles nested keys
# -----------------------------------------------------------------------------


def test_env_overrides_default_separator_nests_cleanly() -> None:
    """The canonical ``MYAPP__DB__HOST`` must nest as ``{'db': {'host': ...}}``.

    ``prefix_value`` is ``prefix.upper().rstrip("_") + "_"`` (config.py:67), a
    single trailing underscore, so ``name[len(prefix_value):]`` (:72) leaves the
    second ``_`` of the ``"__"`` separator attached to the suffix. The suffix
    then splits on ``"__"`` with a leading underscore segment, producing
    ``{'_db': {'host': ...}}`` instead of the documented nested mapping.
    """
    result = env_overrides({"MYAPP__DB__HOST": "x"}, prefix="MYAPP")
    assert result == {"db": {"host": "x"}}


def test_env_overrides_default_separator_flat_key_clean() -> None:
    """A single-segment key after the prefix must not gain a leading underscore.

    ``MYAPP__PORT`` uses the default ``"__"`` separator but contains only one
    path segment after the prefix. The slice bug (:72) still leaves a leading
    underscore, so the key becomes ``'_port'`` instead of ``'port'``.
    """
    result = env_overrides({"MYAPP__PORT": "8080"}, prefix="MYAPP")
    assert result == {"port": "8080"}


# -----------------------------------------------------------------------------
# env.py - non-finite float default bypasses the finiteness guard
# -----------------------------------------------------------------------------


def test_env_non_finite_float_default_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-finite float ``default`` must be rejected like the cast path.

    ``env`` (env.py:41-47) returns an unset variable's ``default`` directly,
    before the finiteness check at :57-60 that applies to cast results. A caller
    passing ``default=float("inf")`` therefore receives ``inf`` silently,
    violating the module's documented finiteness convention.
    """
    monkeypatch.delenv("SEC12_INF_DEFAULT", raising=False)
    with pytest.raises(ValueError):
        env("SEC12_INF_DEFAULT", cast=float, default=float("inf"))


def test_env_non_finite_negative_default_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``-inf`` and ``nan`` defaults must also be rejected, not propagated."""
    monkeypatch.delenv("SEC12_NEG_DEFAULT", raising=False)
    monkeypatch.delenv("SEC12_NAN_DEFAULT", raising=False)
    for default in (float("-inf"), float("nan")):
        with pytest.raises(ValueError):
            env("SEC12_NEG_DEFAULT", cast=float, default=default)


# -----------------------------------------------------------------------------
# Sanity green - normal usage still works
# -----------------------------------------------------------------------------


def test_env_overrides_single_underscore_separator_still_nests() -> None:
    """Sanity green: the explicit ``"_"`` separator still nests correctly."""
    result = env_overrides(
        {"MYAPP_DB_HOST": "x"},
        prefix="MYAPP",
        separator="_",
    )
    assert result == {"db": {"host": "x"}}


def test_env_finite_float_and_non_float_defaults_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity green: finite float and ordinary defaults still resolve."""
    monkeypatch.delenv("SEC12_FINITE_DEFAULT", raising=False)
    assert env("SEC12_FINITE_DEFAULT", cast=float, default=3.5) == 3.5
    monkeypatch.delenv("SEC12_STR_DEFAULT", raising=False)
    assert env("SEC12_STR_DEFAULT", default="fallback") == "fallback"
