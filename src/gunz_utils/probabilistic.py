"""Probabilistic data structures: HyperLogLog, Count-Min Sketch, Counting Bloom Filter, and MinHash."""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Iterable
from typing import Any


def _hash64(item: Any) -> int:
    """Return a uniform 64-bit unsigned integer hash for any item."""
    data = str(item).encode("utf-8")
    digest = hashlib.blake2b(data, digest_size=8).digest()
    return struct.unpack("<Q", digest)[0]


class HyperLogLog:
    """HyperLogLog cardinality estimator with linear counting correction."""

    def __init__(self, p: int = 10) -> None:
        if isinstance(p, bool) or not isinstance(p, int) or not (4 <= p <= 16):
            raise ValueError("precision p must be an integer between 4 and 16")
        self.p = p
        self.m = 1 << p
        self.registers = bytearray(self.m)

        # Alpha constant
        if self.m == 16:
            self._alpha = 0.673
        elif self.m == 32:
            self._alpha = 0.697
        elif self.m == 64:
            self._alpha = 0.709
        else:
            self._alpha = 0.7213 / (1.0 + 1.079 / self.m)

    def add(self, item: Any) -> None:
        """Add an item to the HyperLogLog sketch."""
        x = _hash64(item)
        idx = x & (self.m - 1)
        w = x >> self.p
        # Count leading zeros of (w | 1) up to (64 - p)
        leading = (64 - self.p) if w == 0 else (64 - self.p - w.bit_length() + 1)
        rank = max(1, leading)
        if rank > self.registers[idx]:
            self.registers[idx] = rank

    def cardinality(self) -> int:
        """Estimate the number of distinct elements."""
        z = sum(2.0 ** (-val) for val in self.registers)
        raw_estimate = (self._alpha * (self.m ** 2)) / z

        # Small range correction
        if raw_estimate <= 2.5 * self.m:
            zeros = self.registers.count(0)
            if zeros != 0:
                return round(self.m * math.log(self.m / zeros))
            return round(raw_estimate)

        # Large range correction (for 32-bit bound, blake2b is 64-bit so rarely needed)
        two_32 = 1 << 32
        if raw_estimate > (two_32 / 30.0):
            return round(-two_32 * math.log(1.0 - raw_estimate / two_32))

        return round(raw_estimate)

    def merge(self, other: HyperLogLog) -> HyperLogLog:
        """Merge another HyperLogLog with the same precision."""
        if self.p != other.p:
            raise ValueError(f"cannot merge HyperLogLog with different precision ({self.p} != {other.p})")
        res = HyperLogLog(self.p)
        for i in range(self.m):
            res.registers[i] = max(self.registers[i], other.registers[i])
        return res


class CountMinSketch:
    """Count-Min Sketch for approximate frequency estimation on streams."""

    def __init__(self, width: int = 1024, depth: int = 5) -> None:
        if width < 1 or depth < 1:
            raise ValueError("width and depth must be positive integers")
        self.width = width
        self.depth = depth
        self.table = [[0] * width for _ in range(depth)]

    def _hash(self, item: Any, row: int) -> int:
        h = hashlib.sha256(f"{row}:{item}".encode("utf-8")).digest()
        val = struct.unpack("<I", h[:4])[0]
        return val % self.width

    def add(self, item: Any, count: int = 1) -> None:
        """Increment frequency count of item by count."""
        if count < 0:
            raise ValueError("count must be non-negative")
        for r in range(self.depth):
            c = self._hash(item, r)
            self.table[r][c] += count

    def estimate(self, item: Any) -> int:
        """Query estimated frequency count of item."""
        return min(self.table[r][self._hash(item, r)] for r in range(self.depth))

    def merge(self, other: CountMinSketch) -> CountMinSketch:
        """Merge another Count-Min Sketch of matching dimensions."""
        if self.width != other.width or self.depth != other.depth:
            raise ValueError("dimensions must match to merge CountMinSketch")
        res = CountMinSketch(self.width, self.depth)
        for r in range(self.depth):
            for c in range(self.width):
                res.table[r][c] = self.table[r][c] + other.table[r][c]
        return res


class CountingBloomFilter:
    """Bloom filter supporting element addition, testing, and deletion via 8-bit counters."""

    def __init__(self, capacity: int = 1000, error_rate: float = 0.01) -> None:
        if capacity < 1 or not (0 < error_rate < 1):
            raise ValueError("invalid capacity or error_rate")
        self.capacity = capacity
        self.error_rate = error_rate
        # m = - (n * ln(p)) / (ln(2)^2)
        self.size = max(16, int(-capacity * math.log(error_rate) / (math.log(2) ** 2)))
        # k = (m / n) * ln(2)
        self.hash_count = max(1, int((self.size / capacity) * math.log(2)))
        self.counters = [0] * self.size
        self._count = 0

    def _hashes(self, item: Any) -> list[int]:
        data = str(item).encode("utf-8")
        h1 = struct.unpack("<Q", hashlib.sha256(data).digest()[:8])[0]
        h2 = struct.unpack("<Q", hashlib.md5(data).digest()[:8])[0]
        # Double hashing: gi(x) = (h1 + i * h2) % m
        return [(h1 + i * h2) % self.size for i in range(self.hash_count)]

    def add(self, item: Any) -> None:
        """Add item to filter by incrementing its hash counters."""
        for idx in self._hashes(item):
            if self.counters[idx] < 255:
                self.counters[idx] += 1
        self._count += 1

    def remove(self, item: Any) -> bool:
        """Remove item from filter by decrementing counters. Returns True if item was present."""
        if item not in self:
            return False
        for idx in self._hashes(item):
            if self.counters[idx] > 0:
                self.counters[idx] -= 1
        self._count -= 1
        return True

    def __contains__(self, item: Any) -> bool:
        """Return True if item is possibly in filter, False if definitely not."""
        return all(self.counters[idx] > 0 for idx in self._hashes(item))

    def __len__(self) -> int:
        return self._count


class MinHash:
    """MinHash signature generator for Jaccard similarity estimation between sets."""

    # Mersenne prime 2^61 - 1
    _PRIME = (1 << 61) - 1

    def __init__(self, num_perm: int = 128, seed: int = 42) -> None:
        if num_perm < 1:
            raise ValueError("num_perm must be a positive integer")
        self.num_perm = num_perm
        self.digest = [self._PRIME] * num_perm

        # Generate deterministic pseudo-random linear permutations
        import random
        rng = random.Random(seed)
        self._a = [rng.randint(1, self._PRIME - 1) for _ in range(num_perm)]
        self._b = [rng.randint(0, self._PRIME - 1) for _ in range(num_perm)]

    def update(self, item: Any) -> None:
        """Update signature with an item."""
        x = _hash64(item) % self._PRIME
        for i in range(self.num_perm):
            h = (self._a[i] * x + self._b[i]) % self._PRIME
            if h < self.digest[i]:
                self.digest[i] = h

    def update_batch(self, items: Iterable[Any]) -> None:
        """Update signature with multiple items."""
        for item in items:
            self.update(item)

    def jaccard_similarity(self, other: MinHash) -> float:
        """Estimate the Jaccard similarity [0.0, 1.0] between this and another MinHash."""
        if self.num_perm != other.num_perm:
            raise ValueError("MinHash instances must have the same num_perm")
        matches = sum(1 for a, b in zip(self.digest, other.digest) if a == b)
        return matches / self.num_perm


__all__ = [
    "CountMinSketch",
    "CountingBloomFilter",
    "HyperLogLog",
    "MinHash",
]
