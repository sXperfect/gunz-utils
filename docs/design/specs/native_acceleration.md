# SRS: Native Acceleration and System Utility Primitives
**Definition:** `docs/design/definitions/native_acceleration.yaml`

## 1. Objective and Invariant Contracts

This specification defines the functional behavior, performance bounds, and safety invariants for native C/C++ acceleration in `gunz-utils`.

> [!NOTE]
> All performance benchmarking, micro-profiling, hardware timers, and statistical regression calculations have been consolidated into `gunz-bench` (`native/src/_native_ext.c`). In `gunz-utils`, native acceleration targets core data plumbing and system primitives.

### Invariants

1. **Pure Python Fallback Contract:** Core `gunz-utils` MUST never fail to import, install, or run if a C compiler, native build toolchain, or precompiled binary extension is absent. Every native routine MUST have an identical pure-Python reference fallback.
2. **Equivalence & Contract Invariant:** The observable output of accelerated functions (e.g. `encode_uvarint`, `ByteReader.read_uvarint`) MUST match the pure-Python reference implementation identically, including error exceptions (`ValueError`, `EOFError`).
3. **Zero-Copy & Memory Safety:** C extension routines MUST operate over Python buffer protocol views (`Py_buffer`) without unnecessary heap allocations or memory leaks. All reference counts must strictly conform to CPython conventions.
4. **Canonical Encoding Enforcement:** Varint decoders MUST reject non-canonical encodings (e.g., redundant leading zero bytes) and integers exceeding 64 bits.

---

## 2. Functional Specification

### 2.1 64-bit Unsigned Varint Codec (`gunz_utils.binary`)

#### 2.1.1 Encoding Engine
- **Interface:** `encode_uvarint(value: int) -> bytes`
- **Native Implementation (`gunz_utils._accel.encode_uvarint`):**
  - Accepts unsigned 64-bit integers in the range `[0, 2^64 - 1]`.
  - Encodes directly into a compact stack buffer using standard 7-bit variable-length encoding (MSB set on continuation bytes).
  - Returns a Python `bytes` object of length 1 to 10 bytes.
  - Raises `ValueError` for negative values or values $\ge 2^{64}$.
- **Fallback Implementation:**
  - Pure Python loop in `src/gunz_utils/binary.py`.

#### 2.1.2 Decoding Engine
- **Interface:** `decode_uvarint(buffer: bytes | bytearray | memoryview, offset: int) -> tuple[int, int]`
- **Native Implementation (`gunz_utils._accel.decode_uvarint`):**
  - Parses canonical 64-bit unsigned varints using pointer arithmetic on the underlying contiguous byte buffer.
  - Rejects inputs where the 10th byte exceeds 1 (`ValueError("varint exceeds 64 bits")`).
  - Rejects inputs exceeding 10 bytes without a terminating MSB-clear byte (`ValueError("varint is too long")`).
  - Rejects non-canonical encodings (`ValueError("non-canonical varint")`).
  - Raises `EOFError` if the buffer ends prematurely before a terminating byte.
  - Returns `(value, new_offset)`.
- **Fallback Implementation:**
  - Pure Python byte-by-byte iteration via `ByteReader.read_uvarint()`.
