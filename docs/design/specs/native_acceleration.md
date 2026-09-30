# SRS: Native Acceleration and System Telemetry
**Definition:** `docs/design/definitions/native_acceleration.yaml`

## 1. Objective and Invariant Contracts

This specification defines the functional behavior, performance bounds, and safety invariants for native C/C++ acceleration and low-overhead telemetry in `gunz-utils`.

### Invariants

1. **Pure Python Fallback Contract:** Core `gunz-utils` MUST never fail to import, install, or run if a C compiler, native build toolchain, or precompiled binary extension is absent. Every native routine MUST have an identical pure-Python reference fallback.
2. **Equivalence & Contract Invariant:** The observable output of accelerated functions (e.g. `bootstrap_mean_ci`, process-tree RSS metrics, cycle calibration) MUST match the pure-Python reference implementation within documented numerical tolerances.
3. **Observer Effect Bound:** Telemetry sampling of a child process tree MUST consume $< 0.1\%$ CPU overhead at 50 Hz sampling frequency, generating zero memory allocations in the target process.
4. **Missing Metric Representation:** System metrics not supported by the host OS or permission level MUST be explicitly represented as `None` or `unavailable`, NEVER fabricated as `0`.

---

## 2. Functional Specification

### 2.1 Process-Tree Telemetry (`gunz_utils.telemetry`)

#### 2.1.1 Darwin / macOS Apple Silicon Telemetry
- **Mechanism:** Direct invocation of Darwin kernel C APIs (`libproc.dylib`, `proc_pidinfo`, `proc_listpids`) via the optional C extension `_accel` or standard library `ctypes`.
- **Fields Extracted per PID:**
  - `rss_bytes`: `proc_taskinfo.pti_resident_size`.
  - `cpu_user_seconds`: `proc_taskinfo.pti_total_user / 1e9`.
  - `cpu_system_seconds`: `proc_taskinfo.pti_total_system / 1e9`.
  - `threads`: `proc_taskinfo.pti_threads_count`.
- **Latency Budget:** $< 5 \mu\text{s}$ per PID lookup.

#### 2.1.2 Linux Procfs Fast-Path
- **Mechanism:** Direct POSIX read of `/proc/[pid]/stat` and `/proc/[pid]/smaps_rollup` into fixed stack-allocated byte buffers.
- **Fields Extracted per PID:**
  - `rss_bytes`: Field 24 of `/proc/[pid]/stat` multiplied by `SC_PAGE_SIZE`.
  - `pss_bytes`: `Pss:` line from `smaps_rollup` (if readable; otherwise `None`).
  - `private_bytes`: `Private_Dirty:` + `Private_Clean:` from `smaps_rollup`.
  - `cpu_user_seconds` & `cpu_system_seconds`: Fields 14 & 15 divided by clock ticks.
- **Race Tolerance:** If a child PID terminates during tree traversal, `ProcessLookupError` or `ENOENT` MUST be silently caught and skipped without aborting the parent sample.

---

### 2.2 Vectorized Bootstrap Statistics (`gunz_utils.stats`)

#### 2.2.1 Resampling Engine
- **Interface:** `bootstrap_mean_resamples(data: Sequence[float], num_resamples: int, seed: int) -> list[float]`
- **Native Implementation:**
  - Accepts contiguous float arrays (or zero-copy `Py_buffer` views).
  - Uses a deterministic pseudo-random number generator (PCG32) seeded by the input `seed`.
  - Computes resample means in a SIMD-vectorized C loop.
- **Fallback Implementation:**
  - Pure Python loop using deterministic pseudorandom sampling.

---

### 2.3 Hardware Cycle Counter (`gunz_utils.timing`)

- **Interface:** `hardware_cycle_counter() -> int`
- **Supported Architectures:**
  - ARM64 / Apple Silicon: `mrs %0, cntvct_el0`
  - x86_64: `rdtsc`
- **Fallback:** `time.perf_counter_ns()`
