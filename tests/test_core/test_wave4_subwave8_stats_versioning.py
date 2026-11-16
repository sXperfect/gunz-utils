"""Tests for Wave 4 Sub-Wave 8: Statistics, Versioning & Testkit (#90–#100)."""
# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import logging
import math
import os

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
import pytest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.limits import Limits, ResourceBudget, merge_limits
from gunz_utils.provenance import capture_execution_manifest
from gunz_utils.stats import (
    geometric_mean,
    harmonic_mean,
    kurtosis,
    min_max_scale,
    skewness,
    z_scores,
)
from gunz_utils.testkit import CapturingLogHandler, TemporaryEnvironment
from gunz_utils.versioning import SemanticVersion

# =============================================================================
# #90–#94: Statistical Helpers
# =============================================================================

def test_geometric_mean():
    assert math.isclose(geometric_mean([2.0, 8.0]), 4.0)
    assert math.isclose(geometric_mean([1.0, 3.0, 9.0]), 3.0)
    assert geometric_mean([1.0, 0.0, 5.0]) == 0.0

    with pytest.raises(ValueError, match="empty"):
        geometric_mean([])
    with pytest.raises(ValueError, match="non-negative"):
        geometric_mean([1.0, -2.0])


def test_harmonic_mean():
    assert math.isclose(harmonic_mean([1.0, 2.0, 4.0]), 12.0 / 7.0)
    assert math.isclose(harmonic_mean([60.0, 40.0]), 48.0)

    with pytest.raises(ValueError, match="empty"):
        harmonic_mean([])
    with pytest.raises(ValueError, match="strictly positive"):
        harmonic_mean([1.0, 0.0])


def test_z_scores():
    with pytest.raises(ValueError, match="must not be empty"):
        z_scores([])
    assert z_scores([10.0]) == [0.0]
    assert z_scores([5.0, 5.0, 5.0]) == [0.0, 0.0, 0.0]

    scores = z_scores([10.0, 20.0, 30.0])
    assert math.isclose(scores[0], -1.22474487, rel_tol=1e-5)
    assert math.isclose(scores[1], 0.0, abs_tol=1e-7)
    assert math.isclose(scores[2], 1.22474487, rel_tol=1e-5)


def test_min_max_scale():
    with pytest.raises(ValueError, match="must not be empty"):
        min_max_scale([])
    assert min_max_scale([5.0, 5.0], feature_range=(0.0, 10.0)) == [5.0, 5.0]

    scaled = min_max_scale([10.0, 20.0, 30.0], feature_range=(0.0, 1.0))
    assert math.isclose(scaled[0], 0.0)
    assert math.isclose(scaled[1], 0.5)
    assert math.isclose(scaled[2], 1.0)


def test_skewness_and_kurtosis():
    #? Symmetric data has skewness ~ 0
    sym = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert math.isclose(skewness(sym), 0.0, abs_tol=1e-7)

    #? Right skewed
    right_skew = [1.0, 1.0, 1.0, 2.0, 10.0]
    assert skewness(right_skew) > 0.0

    #? Kurtosis of uniform distribution is negative (platykurtic)
    assert kurtosis([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]) < 0.0

    with pytest.raises(ValueError, match="at least 3 values"):
        skewness([1.0, 2.0])
    with pytest.raises(ValueError, match="at least 4 values"):
        kurtosis([1.0, 2.0, 3.0])


# =============================================================================
# #95: SemanticVersion
# =============================================================================

def test_semantic_version():
    v1 = SemanticVersion.parse("1.2.3")
    assert v1.major == 1
    assert v1.minor == 2
    assert v1.patch == 3
    assert v1.prerelease is None
    assert str(v1) == "1.2.3"

    v1_alpha = SemanticVersion.parse("1.2.3-alpha.1+build.01")
    assert v1_alpha.prerelease == "alpha.1"
    assert v1_alpha.build == "build.01"

    #? Comparison
    assert v1_alpha < v1  #? Prerelease is lower precedence than release
    assert SemanticVersion.parse("1.0.0") < SemanticVersion.parse("2.0.0")
    assert SemanticVersion.parse("1.1.0") < SemanticVersion.parse("1.2.0")
    assert SemanticVersion.parse("1.1.1") < SemanticVersion.parse("1.1.2")
    assert SemanticVersion.parse("1.2.3") == SemanticVersion(1, 2, 3)

    #? Bumping
    assert str(v1.bump_major()) == "2.0.0"
    assert str(v1.bump_minor()) == "1.3.0"
    assert str(v1.bump_patch()) == "1.2.4"


# =============================================================================
# #96: ExecutionManifest Serialization
# =============================================================================

def test_execution_manifest_json_roundtrip():
    manifest = capture_execution_manifest(
        config={"app": "gunz"},
        inputs={"records": 100},
        seed=42,
    )

    json_str = manifest.to_json(indent=2)
    assert '"app": "gunz"' in json_str

    reconstructed = manifest.from_json(json_str)
    assert reconstructed.run_id == manifest.run_id
    assert reconstructed.config == manifest.config
    assert reconstructed.inputs == manifest.inputs
    assert reconstructed.seed == manifest.seed


# =============================================================================
# #97–#98: Limits & ResourceBudget
# =============================================================================

def test_resource_budget_is_exhausted_and_merge_limits():
    l1 = Limits(max_bytes=1000, max_items=50)
    l2 = Limits(max_bytes=500, max_items=100, max_depth=10)
    merged = merge_limits(l1, l2)
    assert merged.max_bytes == 500  #? Strictest (min)
    assert merged.max_items == 50   #? Strictest (min)
    assert merged.max_depth == 10

    budget = ResourceBudget(max_items=2)
    assert not budget.is_exhausted
    budget.consume_items(1)
    assert not budget.is_exhausted
    budget.consume_items(1)
    assert budget.is_exhausted


# =============================================================================
# #99–#100: Testkit Helpers
# =============================================================================

def test_temporary_environment():
    os.environ["GUNZ_TEST_KEY"] = "original"
    with TemporaryEnvironment(GUNZ_TEST_KEY="overridden", GUNZ_NEW_KEY="fresh"):
        assert os.environ["GUNZ_TEST_KEY"] == "overridden"
        assert os.environ["GUNZ_NEW_KEY"] == "fresh"

    assert os.environ["GUNZ_TEST_KEY"] == "original"
    assert "GUNZ_NEW_KEY" not in os.environ


def test_capturing_log_handler():
    logger = logging.getLogger("test_capture_logger")
    logger.setLevel(logging.INFO)

    with CapturingLogHandler(logger) as handler:
        logger.info("message 1: hello")
        logger.warning("message 2: beware")

        assert len(handler.records) == 2
        assert "message 1: hello" in handler.messages[0]
        assert "message 2: beware" in handler.messages[1]

        handler.clear()
        assert len(handler.records) == 0
