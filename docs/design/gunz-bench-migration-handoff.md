# Architectural Handoff: Consolidating Benchmark Capabilities into `gunz-bench`

## 1. Executive Summary

To preserve the architectural integrity of `gunz-utils` as a lean, zero-dependency foundation for the Gunz ecosystem, all domain-specific benchmarking, profiling adapters, visual plotting, and regression gating implementations are being transferred to **`gunz-bench`** (located at `../gunz-bench`).

The entire benchmark subsystem (`src/gunz_utils/benchmark/`, 30 modules) and its test suites have been staged in:
```text
../gunz-bench/tmp/handsoff/
├── MANIFEST.md
├── benchmark_subsystem/
└── tests/
```
accompanied by a comprehensive integration design document in `../gunz-bench/docs/design/gunz-utils-subsystem-transfer.md`.

---

## 2. Strategic Rationale

1. **Elimination of Domain Inversion:**
   `gunz-utils` is defined by its core invariant: *domain-neutral mechanism over application policy*. An entire benchmarking framework (with CLI commands, plot generation, HTML templates, and regression policies) represents an application domain rather than a foundational utility.
2. **Acceleration of `gunz-bench`:**
   `gunz-bench` has an active roadmap requiring Subprocess Isolation (FF-02), Visual Reporting (FF-05), and Historical Drift Analysis (FF-06). Adopting `gunz-utils`'s implementations allows `gunz-bench` to accelerate its development without duplicate engineering.
3. **Removal of Heavy Optional Dependencies:**
   Moving `gunz_utils.benchmark.plot` eliminates the need for `matplotlib` in `gunz-utils`, simplifying CI and packaging matrices.

---

## 3. Migration Roadmap and Deprecation Strategy

### Phase 1: Staging & Handshake (Completed)
- Source code, tests, and documentation staged in `../gunz-bench/tmp/handsoff/`.
- `gunz-bench` design documented in `../gunz-bench/docs/design/gunz-utils-subsystem-transfer.md`.

### Phase 2: Integration in `gunz-bench` (Completed)
- `gunz-bench` merged isolation, reporting, adapters, process trees, and native acceleration.
- `gunz-bench` 0.2.0 released, depending on `gunz-utils>=1.14.0` for core primitives (`atomic_write`, `ResourceBudget`, `GracefulShutdown`, `bootstrap_mean_ci`, `gunz_utils.faults`).
- Downstream performance regression harness wired into `gunz-utils` via `benchmarks/workloads.py` and `scripts/bench.py`.

### Phase 3: Extraction from `gunz-utils` (Current: Deprecated; Complete Removal in Gunz 2.0)
- `gunz_utils.benchmark.*` emits `DeprecationWarning` pointing users to `gunz-bench`.
- `gunz-utils` 2.0.0 will permanently remove `src/gunz_utils/benchmark/` and the optional `plot = ["matplotlib"]` extra.
