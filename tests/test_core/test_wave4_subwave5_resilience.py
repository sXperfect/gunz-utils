"""Tests for Wave 4 Sub-Wave 5: Rate Limiting, Leases & Resilience (#53–#65)."""
from __future__ import annotations

import asyncio
import time
import pytest
from gunz_utils.leases import (
    LeaseHeartbeat,
    LeaseLostError,
    LeaseTiming,
    LeaseToken,
    run_with_lease_heartbeat,
)
from gunz_utils.rate_limit import AsyncRateLimiter, LeakyBucket, RateLimiter
from gunz_utils.resilience import (
    AsyncBulkhead,
    AsyncCircuitBreaker,
    Bulkhead,
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


# =============================================================================
# #53–#56: Rate Limiting
# =============================================================================

def test_sync_rate_limiter():
    limiter = RateLimiter(rate=100.0, capacity=2.0)
    assert limiter.try_acquire(1.0) is True
    assert limiter.try_acquire(1.0) is True
    assert limiter.try_acquire(1.0) is False  # Empty

    # Reset
    limiter.reset()
    assert limiter.try_acquire(1.0) is True

    # Context manager
    with limiter:
        pass


def test_async_rate_limiter_reset():
    async def scenario():
        limiter = AsyncRateLimiter(rate=50.0, capacity=1.0)
        assert await limiter.try_acquire(1.0) is True
        assert await limiter.try_acquire(1.0) is False
        await limiter.reset()
        assert await limiter.try_acquire(1.0) is True

    asyncio.run(scenario())


def test_leaky_bucket():
    bucket = LeakyBucket(capacity=3, leak_rate=100.0)
    assert bucket.try_acquire(1.0) is True
    assert bucket.try_acquire(2.0) is True
    assert bucket.try_acquire(1.0) is False  # capacity reached

    bucket.reset()
    assert bucket.current_level == 0.0
    assert bucket.try_acquire(1.0) is True


# =============================================================================
# #57–#59: Leases
# =============================================================================

def test_lease_timing_dict_serialization():
    timing = LeaseTiming(lease_seconds=10.0, heartbeat_interval=3.0)
    d = timing.to_dict()
    assert d == {"lease_seconds": 10.0, "heartbeat_interval": 3.0}

    rebuilt = LeaseTiming.from_dict(d)
    assert rebuilt == timing


def test_lease_token():
    token = LeaseToken(holder_id="worker-1", expiry_epoch=time.time() + 100.0, fencing_token=1)
    assert token.holder_id == "worker-1"
    assert token.fencing_token == 1
    assert token.is_expired is False

    expired_token = LeaseToken(holder_id="worker-2", expiry_epoch=time.time() - 1.0)
    assert expired_token.is_expired is True

    with pytest.raises(ValueError, match="holder_id must be a non-empty string"):
        LeaseToken(holder_id="", expiry_epoch=100.0)


def test_lease_heartbeat_context_manager():
    async def scenario():
        renewals = 0

        async def renew_fn():
            nonlocal renewals
            renewals += 1
            return True

        async with LeaseHeartbeat(renew=renew_fn, interval=0.01, renew_immediately=True):
            await asyncio.sleep(0.035)

        assert renewals >= 2

    asyncio.run(scenario())


# =============================================================================
# #60–#65: Resilience (CircuitBreaker & Bulkhead)
# =============================================================================

def test_sync_circuit_breaker():
    transitions = []

    def on_change(old_st, new_st):
        transitions.append((old_st, new_st))

    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05, on_state_change=on_change)
    assert cb.state is CircuitState.CLOSED

    # Failure 1
    with pytest.raises(RuntimeError):
        with cb:
            raise RuntimeError("fail 1")
    assert cb.state is CircuitState.CLOSED
    assert cb.failure_count == 1

    # Failure 2 trips breaker
    with pytest.raises(RuntimeError):
        with cb:
            raise RuntimeError("fail 2")
    assert cb.state is CircuitState.OPEN
    assert transitions == [(CircuitState.CLOSED, CircuitState.OPEN)]

    # Open rejects calls
    with pytest.raises(CircuitOpenError):
        with cb:
            pass

    # Reset
    cb.reset()
    assert cb.state is CircuitState.CLOSED
    assert transitions[-1] == (CircuitState.OPEN, CircuitState.CLOSED)


def test_sync_bulkhead():
    bulkhead = Bulkhead(limit=2)
    assert bulkhead.available == 2
    assert bulkhead.active_count == 0

    with bulkhead:
        assert bulkhead.available == 1
        assert bulkhead.active_count == 1
        with bulkhead:
            assert bulkhead.available == 0
            assert bulkhead.active_count == 2

    assert bulkhead.available == 2

    def sample_func(a, b):
        return a + b

    assert bulkhead.run(sample_func, 10, 20) == 30
