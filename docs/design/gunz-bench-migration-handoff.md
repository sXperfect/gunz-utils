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

### Phase 1: Staging & Handshake (Current)
- Source code, tests, and documentation staged in `../gunz-bench/tmp/handsoff/`.
- `gunz-bench` design documented in `../gunz-bench/docs/design/gunz-utils-subsystem-transfer.md`.
- `gunz-utils` retains existing implementations with deprecation notices pointing to `gunz-bench`.

### Phase 2: Integration in `gunz-bench`
- `gunz-bench` merges staged modules into `src/gunz_bench/isolation/`, `src/gunz_bench/adapters/`, and `src/gunz_bench/reporting/`.
- `gunz-bench` configures `gunz-utils` as an optional upstream dependency for core primitives (`atomic_write`, `ResourceBudget`, `GracefulShutdown`, `bootstrap_mean_ci`).

### Phase 3: Extraction from `gunz-utils` (Upcoming Major/Minor Release)
- Deprecate `gunz_utils.benchmark.*` with `GunzDeprecationWarning` pointing users to `gunz-bench`.
- Remove `[project.optional-dependencies] plot = ["matplotlib"]` from `pyproject.toml`.
- Archive historical benchmark tests in `docs/tasks/done/`.
