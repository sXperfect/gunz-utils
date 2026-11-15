"""Arbitrary-length bit array with memory-efficient limb storage and bitwise algebra."""

from __future__ import annotations


class BitSet:
    """Arbitrary-length bitset with O(1) operations and full bitwise algebra."""

    _LIMB_BITS = 64

    def __init__(self, size: int = 0) -> None:
        if size < 0:
            raise ValueError("size must be non-negative")
        self._size = size
        num_limbs = (size + self._LIMB_BITS - 1) // self._LIMB_BITS
        self._limbs: list[int] = [0] * num_limbs

    def __len__(self) -> int:
        return self._size

    def _ensure_capacity(self, index: int) -> None:
        if index >= self._size:
            self._size = index + 1
            needed_limbs = (self._size + self._LIMB_BITS - 1) // self._LIMB_BITS
            while len(self._limbs) < needed_limbs:
                self._limbs.append(0)

    def set(self, index: int, value: bool = True) -> None:
        """Set or clear the bit at index."""
        if index < 0:
            raise IndexError("negative bit index not allowed")
        self._ensure_capacity(index)
        limb_idx = index // self._LIMB_BITS
        bit_idx = index % self._LIMB_BITS
        if value:
            self._limbs[limb_idx] |= 1 << bit_idx
        else:
            self._limbs[limb_idx] &= ~(1 << bit_idx)

    def get(self, index: int) -> bool:
        """Get the boolean value of the bit at index."""
        if index < 0:
            raise IndexError("negative bit index not allowed")
        if index >= self._size:
            return False
        limb_idx = index // self._LIMB_BITS
        bit_idx = index % self._LIMB_BITS
        return bool(self._limbs[limb_idx] & (1 << bit_idx))

    def flip(self, index: int) -> None:
        """Invert the bit at index."""
        self.set(index, not self.get(index))

    def popcount(self) -> int:
        """Return the number of set (1) bits."""
        return sum(limb.bit_count() for limb in self._limbs)

    def __getitem__(self, index: int) -> bool:
        return self.get(index)

    def __setitem__(self, index: int, value: bool) -> None:
        self.set(index, value)

    def __and__(self, other: BitSet) -> BitSet:
        max_size = max(self._size, other._size)
        res = BitSet(max_size)
        min_limbs = min(len(self._limbs), len(other._limbs))
        for i in range(min_limbs):
            res._limbs[i] = self._limbs[i] & other._limbs[i]
        return res

    def __or__(self, other: BitSet) -> BitSet:
        max_size = max(self._size, other._size)
        res = BitSet(max_size)
        for i in range(len(res._limbs)):
            v1 = self._limbs[i] if i < len(self._limbs) else 0
            v2 = other._limbs[i] if i < len(other._limbs) else 0
            res._limbs[i] = v1 | v2
        return res

    def __xor__(self, other: BitSet) -> BitSet:
        max_size = max(self._size, other._size)
        res = BitSet(max_size)
        for i in range(len(res._limbs)):
            v1 = self._limbs[i] if i < len(self._limbs) else 0
            v2 = other._limbs[i] if i < len(other._limbs) else 0
            res._limbs[i] = v1 ^ v2
        return res

    def __invert__(self) -> BitSet:
        res = BitSet(self._size)
        mask = (1 << self._LIMB_BITS) - 1
        for i in range(len(self._limbs)):
            res._limbs[i] = (~self._limbs[i]) & mask
        # Mask off extra bits in last limb
        extra = self._size % self._LIMB_BITS
        if extra != 0 and res._limbs:
            res._limbs[-1] &= (1 << extra) - 1
        return res

    def to_bytes(self) -> bytes:
        """Serialize bitset to compact bytes."""
        byte_len = (self._size + 7) // 8
        out = bytearray(byte_len)
        for i in range(self._size):
            if self.get(i):
                out[i // 8] |= 1 << (i % 8)
        return bytes(out)

    @classmethod
    def from_bytes(cls, data: bytes, size: int | None = None) -> BitSet:
        """Deserialize bitset from compact bytes."""
        effective_size = len(data) * 8 if size is None else size
        bs = cls(effective_size)
        for i in range(effective_size):
            byte_idx = i // 8
            bit_idx = i % 8
            if byte_idx < len(data) and (data[byte_idx] & (1 << bit_idx)):
                bs.set(i, True)
        return bs


__all__ = ["BitSet"]
