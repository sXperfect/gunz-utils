"""Tests for Wave 2 additions: Experiments & Formatting (#15 - #27)."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.experiments import (
    ExperimentMatrix,
    VariantResult,
    metric_improvement,
    parameter_grid,
    run_variant_matrix,
)
from gunz_utils.formatting import (
    escape_terminal,
    format_bytes,
    format_percentage,
    format_table,
    parse_bytes,
    parse_duration,
    supports_color,
)


class TestWave2Experiments(unittest.TestCase):
    def test_item15_variant_result_slots(self) -> None:
        vr = VariantResult(name="v1", metrics={"loss": 0.1})
        self.assertEqual(vr.name, "v1")
        self.assertEqual(vr.metrics, {"loss": 0.1})
        self.assertIsNone(vr.error)
        self.assertFalse(hasattr(vr, "__dict__"))
        self.assertEqual(tuple(vr.__slots__), ("name", "metrics", "error"))

    def test_item16_run_variant_matrix_pre_loop_validation(self) -> None:
        with self.assertRaises(TypeError):
            run_variant_matrix(
    "not_callable", lambda s, c: {}, {
        "baseline": {}})  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            run_variant_matrix(
    lambda: None, "not_callable", {
        "baseline": {}})  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            run_variant_matrix(lambda: None, lambda s, c: {}, [
                               "not_a_mapping"])  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            run_variant_matrix(lambda: None, lambda s, c: {}, {})

    def test_item17_parameter_grid_bare_string_and_generators(self) -> None:
        #? Bare string factor values must be rejected
        with self.assertRaises(TypeError):
            parameter_grid({"mode": "fast"})  # type: ignore[dict-item]

        with self.assertRaises(TypeError):
            parameter_grid({"mode": b"fast"})  # type: ignore[dict-item]

        #? Generator factor values should be consumed safely
        def gen() -> iter:
            yield from (1, 2)

        res = parameter_grid({"num": gen()})
        self.assertEqual(res, [{"num": 1}, {"num": 2}])

        #? Empty generator / sequence
        with self.assertRaises(ValueError):
            parameter_grid({"num": ()})

    def test_item18_metric_improvement_guards(self) -> None:
        matrix = run_variant_matrix(
            lambda: None,
            lambda _s, c: {"loss": c["loss"]},
            {
                "baseline": {"loss": 10.0},
                "better": {"loss": 5.0},
            },
        )

        with self.assertRaises(TypeError):
            metric_improvement(
    "invalid_matrix",
    variant="better",
     metric="loss")  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            metric_improvement(matrix, variant="   ", metric="loss")

        with self.assertRaises(ValueError):
            metric_improvement(matrix, variant="better", metric="   ")

        res = metric_improvement(
    matrix,
    variant="better",
    metric="loss",
     direction="lower")
        self.assertTrue(res["supported"])
        self.assertAlmostEqual(res["relative_improvement"], 0.5)

    def test_item19_experiment_matrix_helpers(self) -> None:
        def run_fn(
            _s: None,
            c: dict[str, object],
        ) -> dict[str, float]:
            if c.get("err"):
                raise ValueError("variant failed")
            return {"score": float(c["score"])}

        matrix = run_variant_matrix(
            lambda: None,
            run_fn,
            {
                "baseline": {"score": 100.0},
                "good": {"score": 110.0},
                "bad": {"err": True},
            },
        )

        self.assertIsInstance(matrix, ExperimentMatrix)
        self.assertEqual(set(matrix.succeeded_variants()), {"baseline", "good"})
        self.assertEqual(matrix.failed_variants(), ("bad",))

        as_dict = matrix.to_dict()
        self.assertIsInstance(as_dict, dict)
        self.assertEqual(as_dict["baseline"], "baseline")


class TestWave2Formatting(unittest.TestCase):
    def test_item20_format_bytes_strict_binary(self) -> None:
        with self.assertRaises(TypeError):
            format_bytes(1024, binary=1)  # type: ignore[arg-type]
        self.assertEqual(format_bytes(1024, binary=True), "1.0 KiB")
        self.assertEqual(format_bytes(1000, binary=False), "1.0 KB")

    def test_item21_parse_bytes(self) -> None:
        with self.assertRaises(TypeError):
            parse_bytes(1024)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            parse_bytes("")
        with self.assertRaises(ValueError):
            parse_bytes("invalid")
        with self.assertRaises(ValueError):
            parse_bytes("100 XB")

        self.assertEqual(parse_bytes("512 B"), 512)
        self.assertEqual(parse_bytes("1.5 KB"), 1500)
        self.assertEqual(parse_bytes("10 MB"), 10_000_000)
        self.assertEqual(parse_bytes("1 KiB"), 1024)
        self.assertEqual(parse_bytes("1.5 MiB"), int(1.5 * 1024 * 1024))
        self.assertEqual(parse_bytes("-500 B"), -500)
        self.assertEqual(parse_bytes("+2 KiB"), 2048)

    def test_item22_parse_duration(self) -> None:
        with self.assertRaises(TypeError):
            parse_duration(123)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            parse_duration("")
        with self.assertRaises(ValueError):
            parse_duration("10 foos")

        self.assertAlmostEqual(parse_duration("250ms"), 0.25)
        self.assertAlmostEqual(parse_duration("500us"), 0.0005)
        self.assertAlmostEqual(parse_duration("1.5s"), 1.5)
        self.assertAlmostEqual(parse_duration("2m 30s"), 150.0)
        self.assertAlmostEqual(parse_duration("1h 15m"), 4500.0)
        self.assertAlmostEqual(parse_duration("1d 2h"), 86400.0 + 7200.0)
        self.assertAlmostEqual(parse_duration("-500ms"), -0.5)

    def test_item23_escape_terminal_trojan_source_and_bidi(self) -> None:
        with self.assertRaises(TypeError):
            escape_terminal(123)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            escape_terminal("hello", multiline="no")  # type: ignore[arg-type]

        #? Trojan Source Bidi overrides: \u202e (RLO)
        dangerous = "access_\u202e_admin"
        escaped = escape_terminal(dangerous)
        self.assertNotIn("\u202e", escaped)
        self.assertIn(r"\u202e", escaped)

        #? Zero-width space: \u200b
        zwsp = "hidden\u200btext"
        self.assertIn(r"\u200b", escape_terminal(zwsp))

        #? BOM: \ufeff
        bom = "\ufeffhello"
        self.assertIn(r"\ufeff", escape_terminal(bom))

    def test_item24_supports_color_dumb_term_and_stream(self) -> None:
        with self.assertRaises(TypeError):
            supports_color(no_color_flag="no")  # type: ignore[arg-type]

        with patch.dict(os.environ, {"TERM": "dumb", "FORCE_COLOR": "0"}, clear=True):
            self.assertFalse(supports_color())

        mock_stream = io.StringIO()
        self.assertFalse(supports_color(stream=mock_stream))

    def test_item25_format_table(self) -> None:
        headers = ["Algorithm", "Ops/sec"]
        rows = [
            ["SHA256", "1,200,000"],
            ["BLAKE2", "2,400,000"],
        ]

        with self.assertRaises(TypeError):
            format_table("Algorithm", rows)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            format_table(headers, ["not_a_row_list"])  # type: ignore[list-item]

        with self.assertRaises(ValueError):
            format_table(headers, rows, alignments=["left"])  #? wrong length

        with self.assertRaises(ValueError):
            format_table(
    headers, rows, alignments=[
        "left", "invalid_align"])  # type: ignore[list-item]

        table = format_table(headers, rows, alignments=["left", "right"])
        self.assertIn("| Algorithm", table)
        self.assertIn("| SHA256", table)
        self.assertIn("---:", table)  #? Right aligned separator

    def test_item26_format_percentage(self) -> None:
        with self.assertRaises(TypeError):
            format_percentage(0.5, signed="yes")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            format_percentage(float("nan"))

        self.assertEqual(format_percentage(0.125, precision=1), "12.5%")
        self.assertEqual(format_percentage(0.125, precision=2, signed=True), "+12.50%")
        self.assertEqual(format_percentage(-0.05, precision=1, signed=True), "-5.0%")
        self.assertEqual(format_percentage(0.0, signed=True), "0.0%")


if __name__ == "__main__":
    unittest.main()
