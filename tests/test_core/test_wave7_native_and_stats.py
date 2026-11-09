"""Tests for Wave 7: Native acceleration, stats primitives, and varint encoding."""

from __future__ import annotations

import math
from unittest import TestCase

from gunz_utils.binary import (
    ByteReader,
    decode_uvarint,
    decode_zigzag,
    encode_uvarint,
    encode_uvarints,
    encode_zigzag,
    encode_zigzags,
)
from gunz_utils.stats import (
    ParetoObjective,
    SummaryStats,
    cosine_similarity,
    ewma,
    pareto_frontier,
    spearman_rank_correlation,
    summarize,
)


class Wave7BinaryBatchVarintsTest(TestCase):
    def test_encode_uvarints_empty_and_roundtrip(self) -> None:
        self.assertEqual(encode_uvarints([]), b"")
        self.assertEqual(encode_uvarints(()), b"")

        values = [0, 1, 127, 128, 255, 300, 16384, 2**64 - 1]
        encoded = encode_uvarints(values)
        expected = b"".join(encode_uvarint(v) for v in values)
        self.assertEqual(encoded, expected)

        reader = ByteReader(encoded)
        decoded = reader.read_uvarints(len(values))
        self.assertEqual(decoded, values)
        self.assertEqual(reader.remaining, 0)

    def test_encode_uvarints_iterable(self) -> None:
        def gen():
            yield from [10, 20, 30]

        encoded = encode_uvarints(gen())
        self.assertEqual(encoded, b"".join(encode_uvarint(v) for v in [10, 20, 30]))

    def test_encode_uvarints_validation(self) -> None:
        with self.assertRaises(TypeError):
            encode_uvarints([1, True, 3])
        with self.assertRaises(TypeError):
            encode_uvarints([1, "two", 3])
        with self.assertRaises(ValueError):
            encode_uvarints([1, -1, 3])
        with self.assertRaises(ValueError):
            encode_uvarints([1, 2**64, 3])

    def test_encode_zigzags_empty_and_roundtrip(self) -> None:
        self.assertEqual(encode_zigzags([]), b"")
        self.assertEqual(encode_zigzags(()), b"")

        values = [0, -1, 1, -64, 64, -(2**63), 2**63 - 1]
        encoded = encode_zigzags(values)
        expected = b"".join(encode_zigzag(v) for v in values)
        self.assertEqual(encoded, expected)

        reader = ByteReader(encoded)
        decoded = reader.read_zigzags(len(values))
        self.assertEqual(decoded, values)
        self.assertEqual(reader.remaining, 0)

    def test_encode_zigzags_validation(self) -> None:
        with self.assertRaises(TypeError):
            encode_zigzags([0, False])
        with self.assertRaises(TypeError):
            encode_zigzags([0, 3.14])
        with self.assertRaises(ValueError):
            encode_zigzags([0, 2**63])
        with self.assertRaises(ValueError):
            encode_zigzags([0, -(2**63) - 1])


class Wave7StatsPrimitivesTest(TestCase):
    def test_summary_stats_iqr(self) -> None:
        stats = summarize([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertIsNotNone(stats.iqr)
        self.assertAlmostEqual(stats.iqr, stats.percentiles[0.75] - stats.percentiles[0.25])

        empty_pct_stats = SummaryStats(
            count=1,
            minimum=1.0,
            maximum=1.0,
            mean=1.0,
            median=1.0,
            variance=0.0,
            stdev=0.0,
            coefficient_of_variation=0.0,
            mad=0.0,
            percentiles={0.5: 1.0},
            outlier_indices=(),
        )
        self.assertIsNone(empty_pct_stats.iqr)

    def test_pareto_frontier_rejects_bool_coordinates(self) -> None:
        objectives = [
            ParetoObjective("cost", lower_is_better=True),
            ParetoObjective("latency", lower_is_better=True),
        ]
        with self.assertRaises(TypeError):
            pareto_frontier([(True, 1.0), (False, 2.0)], objectives=objectives, key=lambda p: p)

    def test_spearman_rank_correlation(self) -> None:
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 20.0, 30.0, 40.0, 50.0]
        self.assertAlmostEqual(spearman_rank_correlation(x, y), 1.0)

        y_inv = [50.0, 40.0, 30.0, 20.0, 10.0]
        self.assertAlmostEqual(spearman_rank_correlation(x, y_inv), -1.0)

        # Ties
        x_ties = [1.0, 2.0, 2.0, 4.0, 5.0]
        y_ties = [5.0, 6.0, 7.0, 8.0, 9.0]
        corr = spearman_rank_correlation(x_ties, y_ties)
        self.assertTrue(0.9 < corr <= 1.0)

        # Constant sequence error
        with self.assertRaises(ValueError):
            spearman_rank_correlation([1.0, 1.0, 1.0], [2.0, 3.0, 4.0])

        # Validation
        with self.assertRaises(ValueError):
            spearman_rank_correlation([1.0], [2.0])
        with self.assertRaises(ValueError):
            spearman_rank_correlation([1.0, 2.0], [3.0])
        with self.assertRaises(TypeError):
            spearman_rank_correlation([1.0, True], [2.0, 3.0])
        with self.assertRaises(ValueError):
            spearman_rank_correlation([1.0, float("nan")], [2.0, 3.0])
        with self.assertRaises(TypeError):
            spearman_rank_correlation("abc", "def")

    def test_cosine_similarity(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0)

        c = [2.0, 2.0]
        d = [4.0, 4.0]
        self.assertAlmostEqual(cosine_similarity(c, d), 1.0)

        e = [1.0, 0.0]
        f = [-1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(e, f), -1.0)

        # Zero norm
        with self.assertRaises(ValueError):
            cosine_similarity([0.0, 0.0], [1.0, 2.0])

        # Empty / unequal length
        with self.assertRaises(ValueError):
            cosine_similarity([], [])
        with self.assertRaises(ValueError):
            cosine_similarity([1.0], [1.0, 2.0])

        # Types and non-finite
        with self.assertRaises(TypeError):
            cosine_similarity([1.0, True], [2.0, 3.0])
        with self.assertRaises(ValueError):
            cosine_similarity([1.0, float("inf")], [2.0, 3.0])

    def test_ewma(self) -> None:
        self.assertEqual(ewma([], alpha=0.5), [])
        self.assertEqual(ewma([10.0], alpha=0.5), [10.0])

        series = [10.0, 20.0, 30.0]
        alpha = 0.5
        # S0 = 10.0
        # S1 = 0.5 * 20.0 + 0.5 * 10.0 = 15.0
        # S2 = 0.5 * 30.0 + 0.5 * 15.0 = 22.5
        smoothed = ewma(series, alpha=alpha)
        self.assertEqual(len(smoothed), 3)
        self.assertAlmostEqual(smoothed[0], 10.0)
        self.assertAlmostEqual(smoothed[1], 15.0)
        self.assertAlmostEqual(smoothed[2], 22.5)

        # Alpha bounds
        with self.assertRaises(ValueError):
            ewma([1.0, 2.0], alpha=0.0)
        with self.assertRaises(ValueError):
            ewma([1.0, 2.0], alpha=1.1)
        with self.assertRaises(TypeError):
            ewma([1.0, 2.0], alpha=True)
        with self.assertRaises(TypeError):
            ewma([1.0, "two"], alpha=0.5)
