# Native Acceleration Architecture in gunz-utils

## 1. Executive Summary and Scope Boundaries

`gunz-utils` serves as the foundational utility layer for reliable, reusable systems across the Gunz ecosystem.

> [!IMPORTANT]
> **Subsystem Boundary Handoff:**
> In accordance with [`docs/design/gunz-bench-migration-handoff.md`](gunz-bench-migration-handoff.md), all domain-specific benchmarking, hardware cycle timing, telemetry process samplers, and statistical performance estimators have been transferred to **`gunz-bench`** (located at `../gunz-bench` with its dedicated C11 extension `native/src/_native_ext.c`).
>
> In `gunz-utils`, native C/C++ acceleration focuses strictly on **domain-neutral, zero-dependency data plumbing and foundational system primitives**.

---

## 2. The Acceleration Hierarchy

To ensure compatibility across all environments (HPC nodes, Alpine Docker containers, PyPy runtimes, local developer laptops), `gunz-utils` employs a tiered execution dispatch via `gunz_utils.buffers.dispatch`:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Tier 0: Pure Python Reference                         │
│  - Standard library only. Guaranteed to run everywhere.                │
│  - Mandatory reference oracle for all property and contract tests.     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Optional enhancement
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              Tier 2: Compiled C Extension (gunz_utils._accel)          │
│  - Optional compiled C extension in C11.                               │
│  - Zero-copy buffer views, bit-level pointer arithmetic.               │
│  - 30x–50x speedup for binary serialization and varint parsing.         │
│  - Fallback to Tier 0 if absent or compilation skipped.                │
└────────────────────────────────────────────────────────────────────────┘
```

### Invariant Rules
- **Zero Mandatory Compiler Dependency:** Installing `gunz-utils` must never fail due to a missing C toolchain (`gcc`, `clang`, MSVC) or Python development headers.
- **Exact Semantic Equivalence:** The native extension must pass the exact same unit, property, and contract tests as the pure-Python reference oracle, raising the identical exceptions (`ValueError`, `EOFError`).

---

## 3. High-Leverage Native Components in gunz-utils

### 3.1 64-bit Unsigned Varint Codec (`gunz_utils.binary`)
- **Problem:** Decoding 64-bit unsigned varints in pure Python requires per-byte bitwise shifting and exception checks in a loop. For high-throughput WALs, streaming events, and binary envelopes, this incurs substantial CPU overhead.
- **Native Implementation:**
  - `decode_uvarint_c`: Unrolled pointer traversal over contiguous `uint8_t*` buffer. Reads up to 10 bytes with strict canonicality validation (rejecting non-canonical leading zero bytes and values exceeding 64 bits).
  * `encode_uvarint_c`: Direct stack-buffered 7-bit variable-length integer encoding.
- **Performance:** 20x–50x reduction in latency per varint operation.

### 3.2 Canonical JSON & Streaming Fingerprinting (`gunz_utils.streaming`)
- **Problem:** Generating canonical deterministic JSON fingerprints involves Python dictionary sorting and string serialization before passing to OpenSSL.
- **Native Target:** Direct zero-copy serialization and streaming SHA-256 updating.

### 3.3 Structural Traversal & Deep Diffing (`gunz_utils.structures`, `gunz_utils.dict_utils`)
- **Problem:** Recursive Python function calls for `deep_diff` and `deep_merge` create call frames and heap allocations for large state snapshots.
- **Native Target:** Recursive C-level mapping comparison with zero-allocation diff reporting.

---

## 4. Implementation and Rollout Strategy

1. **Phase 1: Binary Varints (`gunz_utils.binary`):**
   - Provide `native/include/gunz_utils_native.h` and `native/src/_accel.c`.
   - Provide standalone build script `scripts/build_native.py`.
   - Wire `gunz_utils.binary` to dispatch to `_accel` with pure-Python fallback.
2. **Phase 2: Canonical Streaming Serialization:**
   - Expand `_accel.c` to support streaming digest generation.
3. **Phase 3: Structural Traversal:**
   - Add native fast path for deep structural diffs.
