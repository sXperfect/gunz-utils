"""Phase 42 (security lane) perpetual-audit tests.

Scope: experiments, project, provenance_graph, security, testing, testkit.

Findings (RED):
  1. metric_improvement (experiments.py:256) calls
     ``float(minimum_relative_improvement)`` unguarded. A huge finite int
     (e.g. 10**400) passes the ``isinstance(int | float)`` guard but then
     raises ``OverflowError`` inside the ``math.isfinite`` check, leaking an
     internal OverflowError instead of the documented ``ValueError``.
  2. ManualClock.advance (testkit.py:56-70) surfaces a raw ``OverflowError``
     when a valid finite non-negative ``seconds`` overflows the running clock
     sum (e.g. two advances of 1e308), instead of the documented ``ValueError``
     for the accepted finite-non-negative contract.
"""

from __future__ import annotations

import pytest

from gunz_utils.experiments import (
    compare_numeric_metrics,
    metric_improvement,
    parameter_grid,
    run_variant_matrix,
)
from gunz_utils.provenance_graph import ProvenanceGraph, ProvenanceNode
from gunz_utils.security import NameAccessPolicy, sanitize_filename
from gunz_utils.testkit import (
    ManualClock,
    check_property,
    fuzz_floats,
    fuzz_integers,
    fuzz_json_objects,
)

# ---------------------------------------------------------------------------
# RED: recurring unguarded-float OverflowError -> documented ValueError
# ---------------------------------------------------------------------------

def test_metric_improvement_huge_threshold_raises_valueerror() -> None:
    matrix = {
        "baseline": "b",
        "comparisons": {
            "x": {
                "m": {
                    "numeric": True,
                    "finite": True,
                    "baseline": 10.0,
                    "candidate": 8.0,
                }
            }
        },
    }
    with pytest.raises(ValueError):
        metric_improvement(
            matrix,
            variant="x",
            metric="m",
            direction="lower",
            minimum_relative_improvement=10**400,
        )


def test_manual_clock_advance_overflow_raises_valueerror() -> None:
    clock = ManualClock()
    clock.advance(1e308)
    # A second finite non-negative advance that overflows the running sum must
    # surface as the documented ValueError, not a raw OverflowError.
    with pytest.raises(ValueError):
        clock.advance(1e308)


# ---------------------------------------------------------------------------
# GREEN pins: modules audited and found already correct
# ---------------------------------------------------------------------------

def test_experiments_compare_numeric_metrics_overflow_safe() -> None:
    huge = 10**400
    result = compare_numeric_metrics({"m": 1}, {"m": huge})
    assert result["m"]["relative_delta"] is None
    assert result["m"]["delta"] == huge - 1
    result2 = compare_numeric_metrics({"m": huge}, {"m": 1})
    assert result2["m"]["relative_delta"] is None


def test_experiments_compare_numeric_metrics_bool_categorical() -> None:
    result = compare_numeric_metrics({"m": True}, {"m": False})
    assert result["m"]["numeric"] is False
    assert result["m"]["equal"] is False


def test_experiments_run_variant_matrix_error_type_only() -> None:
    def setup() -> dict:
        return {}

    def run(state: dict, config: dict) -> dict:
        raise ValueError("super-secret-token-123")

    matrix = run_variant_matrix(setup, run, {"baseline": {}, "a": {}, "b": {}})
    assert matrix["results"]["a"].error == "ValueError"
    assert matrix["results"]["a"].metrics == {}


def test_experiments_parameter_grid_validation() -> None:
    with pytest.raises(ValueError):
        parameter_grid({"": [1]})
    with pytest.raises(ValueError):
        parameter_grid({"a": []})
    assert parameter_grid({"a": [1, 2], "b": [3]}) == [
        {"a": 1, "b": 3},
        {"a": 2, "b": 3},
    ]


def test_provenance_rejects_cycle_and_rolls_back() -> None:
    a = ProvenanceNode(identifier="a", kind="k")
    b = ProvenanceNode(identifier="b", kind="k", inputs=("a",))
    graph = ProvenanceGraph((a, b))
    cyclic = ProvenanceNode(identifier="a", kind="k", inputs=("b",))
    with pytest.raises(ValueError):
        graph.add(cyclic)
    # Original a is preserved (rollback), so no cycle was introduced.
    assert graph.get("a") == a


def test_provenance_node_rejects_self_and_duplicate_inputs() -> None:
    with pytest.raises(ValueError):
        ProvenanceNode(identifier="a", kind="k", inputs=("a",))
    with pytest.raises(ValueError):
        ProvenanceNode(identifier="a", kind="k", inputs=("b", "b"))


def test_provenance_metadata_freeze_rejects_cycle() -> None:
    cyclic: dict = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError):
        ProvenanceNode(identifier="a", kind="k", metadata=cyclic)


def test_provenance_ancestors_and_missing_inputs() -> None:
    d = ProvenanceNode(identifier="d", kind="k", inputs=("b", "c", "missing"))
    b = ProvenanceNode(identifier="b", kind="k", inputs=("a",))
    c = ProvenanceNode(identifier="c", kind="k", inputs=("a",))
    a = ProvenanceNode(identifier="a", kind="k")
    graph = ProvenanceGraph((a, b, c, d))
    assert set(graph.ancestors("d")) == {"a", "b", "c"}
    assert graph.missing_inputs("d") == ("missing",)


def test_security_name_access_policy_deny_wins() -> None:
    policy = NameAccessPolicy(allowed=frozenset({"a", "b"}), denied=frozenset({"b"}))
    assert policy.allows("a") is True
    assert policy.allows("b") is False
    with pytest.raises(PermissionError):
        policy.check("c")
    with pytest.raises(ValueError):
        policy.allows("")


def test_security_sanitize_filename_traversal_and_reserved() -> None:
    # Directory components are stripped to the basename; traversal is neutralized.
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("a/../b.txt") == "b.txt"
    assert sanitize_filename("CON") == "_CON"
    with pytest.raises(ValueError):
        sanitize_filename("a" * 5000)
    with pytest.raises(ValueError):
        sanitize_filename("x", replacement="/")


def test_testkit_fuzz_float_overflow_validation() -> None:
    with pytest.raises(ValueError):
        list(fuzz_floats(seed=1, count=1, minimum=10**400))
    with pytest.raises(ValueError):
        list(fuzz_floats(seed=1, count=1, minimum=-1, maximum=10**400))


def test_testkit_fuzz_integer_and_json_bounds() -> None:
    values = list(fuzz_integers(seed=1, count=5, minimum=10, maximum=20))
    assert len(values) == 5
    assert all(10 <= v <= 20 for v in values)
    with pytest.raises(ValueError):
        list(fuzz_integers(seed=1, count=5, minimum=20, maximum=10))
    objects = list(fuzz_json_objects(seed=1, count=3, max_depth=3, max_breadth=3))
    assert len(objects) == 3
    assert all(isinstance(obj, (dict, list)) for obj in objects)


def test_testkit_check_property_counts_examples() -> None:
    total = check_property(
        (i for i in range(5)),
        lambda x: x >= 0,
        max_examples=5,
        seed=1,
    )
    assert total == 5
