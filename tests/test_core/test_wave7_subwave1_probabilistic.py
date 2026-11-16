"""Tests for Wave 7 Sub-Wave 1: Probabilistic Data Structures & Cardinality Estimation.
"""


# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.probabilistic import (
    CountingBloomFilter,
    CountMinSketch,
    HyperLogLog,
    MinHash,
)


def test_hyperloglog_cardinality_and_merge():
    hll1 = HyperLogLog(p=10)
    for i in range(1000):
        hll1.add(f"item_{i}")

    est1 = hll1.cardinality()
    #? Within 10% of true cardinality 1000
    assert 900 <= est1 <= 1100

    hll2 = HyperLogLog(p=10)
    for i in range(1000, 2000):
        hll2.add(f"item_{i}")

    merged = hll1.merge(hll2)
    est_merged = merged.cardinality()
    #? Within 10% of true cardinality 2000
    assert 1800 <= est_merged <= 2200


def test_count_min_sketch():
    cms = CountMinSketch(width=500, depth=5)
    cms.add("apple", 10)
    cms.add("banana", 5)
    cms.add("apple", 2)

    assert cms.estimate("apple") >= 12
    assert cms.estimate("banana") >= 5
    assert cms.estimate("orange") <= 2


def test_counting_bloom_filter_add_and_remove():
    cbf = CountingBloomFilter(capacity=100, error_rate=0.01)
    cbf.add("test_key")
    assert "test_key" in cbf
    assert "missing_key" not in cbf
    assert len(cbf) == 1

    #? Remove
    assert cbf.remove("test_key")
    assert "test_key" not in cbf
    assert len(cbf) == 0


def test_minhash_similarity():
    s1 = {"apple", "banana", "cherry", "date", "fig"}
    s2 = {"apple", "banana", "cherry", "date", "grape"}  #? 4/6 = 0.666 Jaccard
    s3 = {"kiwi", "lemon", "mango", "orange", "peach"}  #? 0 Jaccard

    m1 = MinHash(num_perm=128, seed=42)
    m2 = MinHash(num_perm=128, seed=42)
    m3 = MinHash(num_perm=128, seed=42)

    m1.update_batch(s1)
    m2.update_batch(s2)
    m3.update_batch(s3)

    sim12 = m1.jaccard_similarity(m2)
    sim13 = m1.jaccard_similarity(m3)

    assert 0.5 <= sim12 <= 0.8
    assert sim13 < 0.1
