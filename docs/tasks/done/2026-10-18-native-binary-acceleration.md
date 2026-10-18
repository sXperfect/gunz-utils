# Task: Native C Binary Acceleration (Zigzag Codec & Batch Varint Decoding)

## Status: Done
- **Date**: 2026-10-18
- **Scope**: `native/include/gunz_utils_native.h`, `native/src/_accel.c`, `src/gunz_utils/binary.py`, `tests/test_core/test_binary_accel.py`, `docs/audits/algorithm-registry.md`
- **Algorithm ID**: **ALG-094** (Level **A4**)
- **Owner**: Antigravity Pair Programmer

---

## 1. Summary of Changes
1. **C Header & Implementation (`native/include/gunz_utils_native.h`, `native/src/_accel.c`)**:
   - Implemented `gunz_native_encode_zigzag` and `gunz_native_decode_zigzag` for signed 64-bit integers mapping to canonical MSB continuation varints via `(v << 1) ^ (v >> 63)`.
   - Implemented Python C API extension wrappers:
     - `py_encode_zigzag(value)`: fast encode signed 64-bit int to `bytes`.
     - `py_decode_zigzag(buffer, offset)`: zero-copy decode to `(int, new_offset)`.
     - `py_fast_decode_uvarints(buffer, offset, count)`: batch decode unsigned varints directly in C with transactional rollback on error or EOF.
     - `py_fast_decode_zigzags(buffer, offset, count)`: batch decode signed zigzag varints in C with transactional rollback.
   - Registered all routines in `AccelMethods` table.
2. **Pure Python Fallback & Module Integration (`src/gunz_utils/binary.py`)**:
   - Extended `ByteReader` with:
     - `read_zigzag() -> int`: single signed 64-bit integer.
     - `read_uvarints(count: int) -> list[int]`: transactional batch unsigned read.
     - `read_zigzags(count: int) -> list[int]`: transactional batch signed read.
   - Added module-level standalone functions:
     - `encode_zigzag(value: int) -> bytes`
     - `decode_uvarint(data, offset=0) -> tuple[int, int]`
     - `decode_zigzag(data, offset=0) -> tuple[int, int]`
   - Maintained 100% observable equivalence between native C acceleration and pure-Python reference implementations.
3. **Audits & Verification**:
   - Registered ALG-094 at Level A4 in `docs/audits/algorithm-registry.md`.
   - Comprehensive test suite in `tests/test_core/test_binary_accel.py` covering boundary conditions (`-2^63`, `2^63-1`, `0`, `-1`, `1`), boolean and float rejection, non-canonical zero rejection, overflow and EOF transactional rollback, and fallback monkeypatch differential testing.
   - 100% test pass rate (1,888 passed in pytest), zero `gunz-style` violations, zero `ruff` errors, zero `mypy` strict errors.
