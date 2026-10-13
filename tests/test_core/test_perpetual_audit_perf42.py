"""Phase 42 perpetual audit: round-4 (deepest) re-audit of six core modules.

experiments.py, project.py, provenance_graph.py, security.py, testing.py,
testkit.py.

Verified correct at base 6204aa5 (GREEN companion tests below):
- experiments: run_variant_matrix, compare_numeric_metrics (bool/int
  categorical handling, overflow-safe relative_delta), parameter_grid.
- project: resolve_project_root backward-compat re-export.
- provenance_graph: add/get/ancestors/lineage/missing_inputs, cycle rejection,
  transactional add rollback, node validation.
- security: sanitize_filename, safe_path_join containment, NameAccessPolicy
  (perf/correctness scope; security concerns are the sec lane's).
- testing: temporary_env, eventually/eventually_async poll validation.
- testkit: ManualClock, fuzz_* generators, check_property, PropertyFailure.

One NEW finding (recurring unguarded-float OverflowError class):

1) experiments.metric_improvement (src/gunz_utils/experiments.py:253-261)
   validates minimum_relative_improvement with
   ``not math.isfinite(float(minimum_relative_improvement))`` -- an unguarded
   float conversion. For a huge int like 10**400, ``float(x)`` raises
   OverflowError before the guard can return False, so
   ``metric_improvement(..., minimum_relative_improvement=10**400)`` leaks
   OverflowError instead of the documented ValueError. Booleans and negative
   values are correctly rejected as ValueError; only the huge-int overflow
   path leaks (RED).

This test is expected to be RED against base 6204aa5 for the finding and GREEN
for the companion behaviors.
"""

from __future__ import annotations

import os

import pytest
from gunz_utils import experiments
from gunz_utils.project import resolve_project_root
from gunz_utils.provenance_graph import ProvenanceGraph, ProvenanceNode
from gunz_utils.security import NameAccessPolicy, safe_path_join, sanitize_filename
from gunz_utils.testing import temporary_env
from gunz_utils.testkit import (
    ManualClock,
    PropertyFailure,
    check_property,
    fuzz_floats,
    fuzz_integers,
    fuzz_strings,
)

# ---------------------------------------------------------------------------
# 1) experiments.metric_improvement unguarded-float OverflowError (RED)
# ---------------------------------------------------------------------------


def test_metric_improvement_huge_threshold_raises_valueerror():
    matrix = {
        "baseline": "b",
        "results": {},
        "comparisons": {
            "v": {
                "m": {
                    "numeric": True,
                    "finite": True,
                    "baseline": 10.0,
                    "candidate": 5.0,
                }
            }
        },
    }
    with pytest.raises(ValueError):
        experiments.metric_improvement(
            matrix,
            variant="v",
            metric="m",
            minimum_relative_improvement=10**400,
        )


def test_metric_improvement_rejects_bool_and_negative():
    matrix = {
        "baseline": "b",
        "results": {},
        "comparisons": {
            "v": {
                "m": {
                    "numeric": True,
                    "finite": True,
                    "baseline": 10.0,
                    "candidate": 5.0,
                }
            }
        },
    }
    with pytest.raises(ValueError):
        experiments.metric_improvement(
            matrix, variant="v", metric="m", minimum_relative_improvement=True
        )
    with pytest.raises(ValueError):
        experiments.metric_improvement(
            matrix, variant="v", metric="m", minimum_relative_improvement=-0.5
        )


# ---------------------------------------------------------------------------
# GREEN companions — experiments
# ---------------------------------------------------------------------------


def test_run_variant_matrix_and_compare():
    def setup() -> dict:
        return {"x": []}

    def run(state: dict, config: dict) -> dict:
        state["x"].append(config["n"])
        return {"sum": sum(state["x"])}

    out = experiments.run_variant_matrix(
        setup,
        run,
        {"baseline": {"n": 1}, "v2": {"n": 2}},
    )
    assert out["baseline"] == "baseline"
    assert out["results"]["baseline"].metrics == {"sum": 1}
    assert out["comparisons"]["v2"]["sum"]["numeric"] is True
    assert out["comparisons"]["v2"]["sum"]["delta"] == 1


def test_compare_numeric_metrics_bool_and_overflow():
    assert (
        experiments.compare_numeric_metrics({"a": True}, {"a": 1})["a"]["numeric"]
        is False
    )
    cmp = experiments.compare_numeric_metrics({"a": 10**400}, {"a": 10**400 + 1})
    assert cmp["a"]["finite"] is True
    assert cmp["a"]["relative_delta"] == 0.0  # 1 / inf-denominator -> 0.0


def test_parameter_grid():
    grid = experiments.parameter_grid({"a": [1, 2], "b": ["x", "y"]})
    assert len(grid) == 4
    assert grid[0] == {"a": 1, "b": "x"}
    assert experiments.parameter_grid({}) == [{}]
    with pytest.raises(ValueError):
        experiments.parameter_grid({"a": []})


# ---------------------------------------------------------------------------
# GREEN companions — project
# ---------------------------------------------------------------------------


def test_project_reexport_resolvable():
    from gunz_utils import resolve_project_root as root_impl

    assert resolve_project_root is root_impl
    assert callable(resolve_project_root)


# ---------------------------------------------------------------------------
# GREEN companions — provenance_graph
# ---------------------------------------------------------------------------


def test_provenance_graph_add_ancestors_cycle():
    g = ProvenanceGraph()
    a = ProvenanceNode(identifier="a", kind="k")
    b = ProvenanceNode(identifier="b", kind="k", inputs=("a",))
    g.add(a)
    g.add(b)
    assert set(g.ancestors("b")) == {"a"}
    assert g.lineage("b")[0].identifier == "b"
    assert g.missing_inputs("b") == ()
    c = ProvenanceNode(identifier="c", kind="k", inputs=("a",))
    g.add(c)
    # introducing a cycle must be rejected and roll back
    back = ProvenanceNode(identifier="a", kind="k", inputs=("b",))
    with pytest.raises(ValueError):
        g.add(back, replace=True)
    assert g.get("a").inputs == ()


def test_provenance_node_validation():
    with pytest.raises(ValueError):
        ProvenanceNode(identifier="", kind="k")
    with pytest.raises(ValueError):
        ProvenanceNode(identifier="a", kind="k", inputs=("a",))  # self-dependency
    with pytest.raises(ValueError):
        ProvenanceNode(identifier="a", kind="k", inputs=("b", "b"))  # dup inputs


# ---------------------------------------------------------------------------
# GREEN companions — security (perf/correctness scope)
# ---------------------------------------------------------------------------


def test_security_helpers():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("report v2.txt") == "report_v2.txt"
    with pytest.raises(ValueError):
        sanitize_filename("." * 4096)
    with pytest.raises(ValueError):
        safe_path_join("/tmp", "../escape")


def test_name_access_policy():
    policy = NameAccessPolicy(
        allowed=frozenset({"run", "plan"}), denied=frozenset({"plan"})
    )
    assert policy.allows("run") is True
    assert policy.allows("plan") is False
    assert policy.allows("other") is False
    with pytest.raises(PermissionError):
        policy.check("plan")


# ---------------------------------------------------------------------------
# GREEN companions — testing
# ---------------------------------------------------------------------------


def test_temporary_env_restores():
    os.environ["GUNZ_TEST_42"] = "before"
    try:
        with temporary_env({"GUNZ_TEST_42": "after", "GUNZ_TEST_NEW": "x"}):
            assert os.environ["GUNZ_TEST_42"] == "after"
        assert os.environ["GUNZ_TEST_42"] == "before"
    finally:
        os.environ.pop("GUNZ_TEST_42", None)
        os.environ.pop("GUNZ_TEST_NEW", None)


def test_testing_validate_poll_args():
    from gunz_utils.testing import eventually

    with pytest.raises(ValueError):
        eventually(lambda: True, timeout=-1)
    with pytest.raises(ValueError):
        eventually(lambda: True, interval=0)
    with pytest.raises(ValueError):
        eventually(lambda: True, timeout=10**400)


# ---------------------------------------------------------------------------
# GREEN companions — testkit
# ---------------------------------------------------------------------------


def test_manual_clock():
    clock = ManualClock(now=10.0)
    assert clock.monotonic() == 10.0
    clock.advance(2.5)
    assert clock.monotonic() == 12.5
    with pytest.raises(ValueError):
        clock.advance(10**400)


def test_fuzz_generators_deterministic_and_bounded():
    assert list(fuzz_integers(seed=1, count=5)) == list(fuzz_integers(seed=1, count=5))
    floats = list(fuzz_floats(seed=1, count=50, allow_infinity=False, allow_nan=False))
    assert all(not (f != f or abs(f) == float("inf")) for f in floats)
    assert len(list(fuzz_strings(seed=1, count=10, max_length=8))) == 10
    with pytest.raises(ValueError):
        list(fuzz_integers(seed=1, count=-1))


def test_check_property():
    samples = list(fuzz_integers(seed=1, count=10, minimum=0, maximum=100))
    assert check_property(iter(samples), lambda _: True) == len(samples)
    with pytest.raises(PropertyFailure):
        check_property(iter([1, 2, 3]), lambda x: x < 3, seed=7)
