"""Tests for Wave 6 Sub-Wave 5: Advanced Rate Limiting Algorithms."""

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.rate_limit import (
    BurstTokenBucket,
    LeakyBucket,
    RateLimitExceeded,
    SlidingWindowLog,
    rate_limited,
)


def test_leaky_bucket_acquire():
    bucket = LeakyBucket(capacity=2, leak_rate=10.0)
    assert bucket.acquire(1.0)
    assert bucket.acquire(1.0)
    assert not bucket.try_acquire(1.0)

    #? Reset
    bucket.reset()
    assert bucket.try_acquire(1.0)


def test_sliding_window_log():
    sw = SlidingWindowLog(max_requests=3, window_seconds=1.0)
    assert sw.allow("user1")
    assert sw.allow("user1")
    assert sw.remaining("user1") == 1
    assert sw.allow("user1")
    assert not sw.allow("user1")
    assert sw.remaining("user1") == 0

    #? Independent key
    assert sw.allow("user2")

    sw.reset("user1")
    assert sw.remaining("user1") == 3


def test_burst_token_bucket():
    tb = BurstTokenBucket(rate=5.0, base_capacity=2.0, peak_capacity=5.0)
    assert tb.consume(1.0)
    assert tb.consume(1.0)
    assert not tb.consume(1.0)


def test_rate_limited_decorator():
    sw = SlidingWindowLog(max_requests=2, window_seconds=1.0)

    @rate_limited(sw)
    def api_call():
        return "success"

    assert api_call() == "success"
    assert api_call() == "success"
    with pytest.raises(RateLimitExceeded):
        api_call()
