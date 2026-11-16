"""Tests for Wave 4 Sub-Wave 7: Sampling, Faults & Diagnostics (#78–#89)."""
# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import io
import random

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
import pytest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.diagnostics import (
    capture_system_diagnostics,
    format_exception_summary,
    get_exception_chain,
    sanitize_traceback,
)
from gunz_utils.faults import (
    CorruptingWriter,
    FailAfter,
    InjectedFault,
    LatencyInjector,
)
from gunz_utils.sampling import (
    bernoulli_sample,
    hash_sample_fraction,
    reservoir_sample,
)

# =============================================================================
# #78–#81: Sampling helpers
# =============================================================================

def test_reservoir_sample():
    stream = range(100)
    rng = random.Random(42)
    sample = reservoir_sample(stream, 5, rng=rng)
    assert len(sample) == 5
    assert all(x in range(100) for x in sample)

    #? Stream smaller than k returns full stream
    assert reservoir_sample([1, 2, 3], 10) == [1, 2, 3]

    with pytest.raises(ValueError, match="positive integer"):
        reservoir_sample([1, 2], 0)
    with pytest.raises(ValueError, match="positive integer"):
        reservoir_sample([1, 2], -1)


def test_bernoulli_sample():
    items = list(range(100))
    rng = random.Random(42)

    #? p = 0.0 yields nothing
    assert list(bernoulli_sample(items, 0.0, rng=rng)) == []

    #? p = 1.0 yields everything
    assert list(bernoulli_sample(items, 1.0, rng=rng)) == items

    #? p = 0.5 yields roughly half
    sampled = list(bernoulli_sample(items, 0.5, rng=rng))
    assert 20 < len(sampled) < 80

    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        list(bernoulli_sample(items, 1.5))


def test_hash_sample_fraction():
    assert hash_sample_fraction("item1", 0.0) is False
    assert hash_sample_fraction("item1", 1.0) is True

    #? Same item with same fraction and seed is deterministic
    res1 = hash_sample_fraction("user-12345", 0.5, seed=10)
    res2 = hash_sample_fraction("user-12345", 0.5, seed=10)
    assert res1 == res2


# =============================================================================
# #82–#84: Fault injection
# =============================================================================

def test_latency_injector():
    async def scenario():
        injector = LatencyInjector(min_delay=0.005, max_delay=0.01)
        d = injector.inject()
        assert 0.005 <= d <= 0.01

        d_async = await injector.ainject()
        assert 0.005 <= d_async <= 0.01

    asyncio.run(scenario())


def test_corrupting_writer():
    target = io.BytesIO()
    writer = CorruptingWriter(target, corrupt_every_n_bytes=4)

    #? Write 8 bytes
    data = b"12345678"
    written = writer.write(data)
    assert written == 8

    res = target.getvalue()
    assert len(res) == 8
    #? Bytes 0..2 unchanged: '1', '2', '3'
    assert res[:3] == b"123"
    #? Byte 3 corrupted
    assert res[3] != ord("4")
    #? Bytes 4..6 unchanged: '5', '6', '7'
    assert res[4:7] == b"567"
    #? Byte 7 corrupted
    assert res[7] != ord("8")


def test_fail_after_reset():
    fault = FailAfter(successes=1, exception_factory=lambda: InjectedFault("boom"))
    fault()  #? call 1: ok
    with pytest.raises(InjectedFault):
        fault()  #? call 2: raises

    fault.reset()
    assert fault.calls == 0
    fault()  #? call 1 again after reset: ok


# =============================================================================
# #85–#89: Diagnostics
# =============================================================================

def test_format_exception_summary():
    try:
        raise ValueError("bad configuration key")
    except ValueError as exc:
        summary = format_exception_summary(exc)
        assert summary.startswith("ValueError: bad configuration key at ")


def test_capture_system_diagnostics():
    diag = capture_system_diagnostics()
    assert "python_version" in diag
    assert "platform" in diag
    assert "pid" in diag
    assert "thread_count" in diag
    assert "gc_counts" in diag
    assert diag["thread_count"] >= 1


def test_sanitize_traceback():
    raw_tb = ("Traceback (most recent call last):\n  File 'app.py', line "
        "10\n    api_key = 'sk_live_secret12345'\nValueError: bad")
    clean = sanitize_traceback(raw_tb)
    assert "Traceback" in clean
    assert "api_key" in clean
    assert "sk_live_secret12345" not in clean
    assert "***" in clean


def test_get_exception_chain_cycle_safe():
    e1 = ValueError("e1")
    e2 = RuntimeError("e2")
    e1.__cause__ = e2
    #? Create cycle
    e2.__cause__ = e1

    chain = get_exception_chain(e1)
    #? Must terminate without infinite loop
    assert chain == [e1, e2]
