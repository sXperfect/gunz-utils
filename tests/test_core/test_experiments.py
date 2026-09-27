"""Tests for pristine-state variant experiments."""

from __future__ import annotations

import math

import pytest

from gunz_utils.experiments import (
    compare_numeric_metrics,
    metric_improvement,
    parameter_grid,
    run_variant_matrix,
)


def test_run_variant_matrix_rebuilds_state_per_variant() -> None:
    setup_calls: list[int] = []

    def setup() -> dict[str, float]:
        setup_calls.append(1)
        return {"base": 10.0}

    def run(
        state: dict[str, float],
        config: dict[str, object],
    ) -> dict[str, float]:
        return {"loss": state["base"] * float(config["scale"])}

    matrix = run_variant_matrix(
        setup,
        run,
        {
            "baseline": {"scale": 1.0},
            "half": {"scale": 0.5},
        },
    )

    assert len(setup_calls) == 2
    assert matrix["results"]["baseline"].metrics["loss"] == pytest.approx(10.0)
    assert matrix["results"]["half"].metrics["loss"] == pytest.approx(5.0)


def test_run_variant_matrix_captures_candidate_failure() -> None:
    def run(
        _state: None,
        config: dict[str, object],
    ) -> dict[str, float]:
        if bool(config["fail"]):
            raise RuntimeError("boom")
        return {"value": 1.0}

    matrix = run_variant_matrix(
        lambda: None,
        run,
        {
            "baseline": {"fail": False},
            "broken": {"fail": True},
        },
    )

    assert matrix["results"]["broken"].error is not None
    assert "broken" not in matrix["comparisons"]


def test_run_variant_matrix_requires_baseline() -> None:
    with pytest.raises(KeyError, match="baseline"):
        run_variant_matrix(
            lambda: None,
            lambda _state, _config: {},
            {"candidate": {}},
        )


def test_compare_numeric_metrics_preserves_structure_and_bool_semantics() -> None:
    result = compare_numeric_metrics(
        {
            "loss": 10.0,
            "enabled": True,
            "only_baseline": 1,
        },
        {
            "loss": 8.0,
            "enabled": False,
            "only_candidate": 2,
        },
    )

    assert result["loss"]["delta"] == pytest.approx(-2.0)
    assert result["loss"]["relative_delta"] == pytest.approx(-0.2)
    assert not result["enabled"]["numeric"]
    assert not result["enabled"]["equal"]
    assert result["only_baseline"]["missing_candidate"]
    assert result["only_candidate"]["missing_baseline"]


def test_metric_improvement_supports_lower_and_higher_metrics() -> None:
    matrix = {
        "comparisons": {
            "candidate": {
                "loss": {
                    "numeric": True,
                    "finite": True,
                    "baseline": 10.0,
                    "candidate": 5.0,
                },
                "throughput": {
                    "numeric": True,
                    "finite": True,
                    "baseline": 100.0,
                    "candidate": 125.0,
                },
            }
        }
    }

    lower = metric_improvement(
        matrix,
        variant="candidate",
        metric="loss",
        direction="lower",
        minimum_relative_improvement=0.4,
    )
    higher = metric_improvement(
        matrix,
        variant="candidate",
        metric="throughput",
        direction="higher",
        minimum_relative_improvement=0.2,
    )

    assert lower["supported"]
    assert lower["relative_improvement"] == pytest.approx(0.5)
    assert higher["supported"]
    assert higher["relative_improvement"] == pytest.approx(0.25)


def test_metric_improvement_rejects_nonfinite_comparison() -> None:
    matrix = {
        "comparisons": {
            "candidate": {
                "loss": {
                    "numeric": True,
                    "finite": False,
                    "baseline": 1.0,
                    "candidate": math.nan,
                }
            }
        }
    }

    result = metric_improvement(
        matrix,
        variant="candidate",
        metric="loss",
    )

    assert not result["supported"]
    assert "non-finite" in result["reason"]



def test_run_variant_matrix_deep_copies_nested_configurations() -> None:
    variants = {
        "baseline": {
            "nested": {
                "values": [1, 2],
            }
        },
        "candidate": {
            "nested": {
                "values": [3, 4],
            }
        },
    }

    def run(
        _state: None,
        config: dict[str, object],
    ) -> dict[str, float]:
        nested = config["nested"]
        assert isinstance(nested, dict)
        values = nested["values"]
        assert isinstance(values, list)
        values.append(99)
        return {"count": float(len(values))}

    run_variant_matrix(
        lambda: None,
        run,
        variants,
    )

    assert variants["baseline"]["nested"]["values"] == [1, 2]
    assert variants["candidate"]["nested"]["values"] == [3, 4]


def test_run_variant_matrix_does_not_store_exception_message() -> None:
    def run(
        _state: None,
        _config: dict[str, object],
    ) -> dict[str, float]:
        raise RuntimeError("token=super-secret")

    matrix = run_variant_matrix(
        lambda: None,
        run,
        {
            "baseline": {},
        },
    )

    assert matrix["results"]["baseline"].error == "RuntimeError"
    assert "super-secret" not in (
        matrix["results"]["baseline"].error or ""
    )



def test_parameter_grid_returns_cartesian_combinations() -> None:
    grid = parameter_grid(
        {
            "optimizer": ["sgd", "adam"],
            "precision": ["fp32", "bf16"],
        }
    )

    assert grid == [
        {"optimizer": "sgd", "precision": "fp32"},
        {"optimizer": "sgd", "precision": "bf16"},
        {"optimizer": "adam", "precision": "fp32"},
        {"optimizer": "adam", "precision": "bf16"},
    ]


def test_parameter_grid_empty_mapping_has_one_empty_combination() -> None:
    assert parameter_grid({}) == [{}]


def test_parameter_grid_rejects_empty_factor_values() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        parameter_grid(
            {"empty": []}
        )
