# Benchmarking and Profiling Tool Landscape

## Purpose

`gunz-utils` is the common orchestration, normalization, provenance, reporting,
and regression layer for performance engineering across Gunz repositories. It
should not replace mature specialist profilers when they provide deeper or more
reliable measurements.

The preferred architecture is:

```text
project benchmark/profile definition
              |
              v
        gunz-utils SDK
              |
     +--------+---------+----------+
     |        |         |          |
   native   pyperf   hyperfine   profiler adapters
   runner                         perf/memray/py-spy/
                                  scalene/heaptrack
     |        |         |          |
     +--------+---------+----------+
              |
       normalized artifacts
              |
      history / comparison
              |
       plots / HTML / CI gate
```

## Tool decisions

| Tool | Reuse directly | Reimplement in gunz-utils | Do not duplicate |
|---|---|---|---|
| pyperf | Worker isolation, calibration, stability checks, system metadata/tuning, Python benchmark JSON | Adapter into Gunz result/history/report schema; common provenance; unified comparison UI | Its calibration/worker methodology and system tuning |
| hyperfine | Arbitrary-command repeated timing, warmups, parameter scans, setup/prepare/cleanup, outlier handling | Native argv-based runner for low-overhead embedded use; import Hyperfine JSON; unified parameter/result schema | Mature shell-oriented CLI UX and statistical runner |
| Linux perf | Hardware/software counters, sampling, call graphs | Thin structured adapters, capability detection, normalized counters/artifact references | PMU collection, stack unwinding, kernel integration |
| Memray | Python/native allocation tracing and allocation flamegraphs | Adapter/launcher, artifact registration, normalized summary fields | Allocation interception, native stack tracking, reporters |
| py-spy | Low-overhead external Python sampling, subprocess/native options, flamegraph/speedscope output | Adapter, process/artifact metadata, common report links | Python interpreter stack sampling |
| Scalene | Python CPU/memory profiling and Python-vs-native attribution | Adapter and normalized summaries where stable machine-readable output exists | Sampling engine and language attribution |
| heaptrack | Native heap allocations, stack traces, leaks/hotspots | Adapter, artifact discovery, summary normalization | malloc/free interception and native heap analysis |
| pytest-benchmark | Benchmark integration with pytest and developer test workflows | Import/export adapter and common regression policy | pytest plugin behavior |
| ASV | Long-running benchmark history, environment matrices, web history | Optional import/history adapter; Gunz can remain lighter for ordinary repos | Full environment/build matrix and static history site |
| pyperformance | Standard Python benchmark suites built on pyperf | Optional ingestion for runtime/interpreter comparisons | Standard benchmark corpus |

## What to reuse

### pyperf

Use pyperf as the preferred backend for rigorous Python microbenchmarks. It
automatically calibrates loop counts, runs multiple worker processes, records
metadata, detects unstable results, supports memory tracking, stores JSON, and
provides statistical comparison.

Gunz should add a `PyperfBackend` that:

1. invokes pyperf or accepts an existing pyperf JSON artifact;
2. preserves the original artifact unchanged;
3. maps runs/values/metadata into the Gunz normalized model;
4. records Git and project metadata;
5. exposes the result through Gunz history/plot/report APIs.

Do not reproduce pyperf's calibration or system-tuning logic.

### hyperfine

Use Hyperfine as the preferred mature repeated-command backend. Its useful
capabilities include warmups, automatic run selection, parameter scans,
setup/prepare/conclude/cleanup hooks, outlier detection, and JSON/CSV/Markdown
export.

Gunz should retain its own direct argv runner because it avoids shell parsing,
has very low integration overhead, and can synchronously collect the existing
`/proc` process-tree samples. Add a Hyperfine adapter when statistically mature
repeated command timing or parameter sweeps are requested.

### Linux perf

Keep the existing thin `perf` adapter. This is the correct abstraction:
`gunz-utils` owns invocation, structured parsing, provenance, artifact
registration, and comparison while Linux perf owns PMU/kernel measurement.

Derived Gunz metrics can add value without duplicating perf:

- IPC = instructions / cycles;
- branch-miss rate;
- cache-miss rate;
- context switches per second;
- cycles per operation when an operation count is supplied.

### Memray

Use Memray for allocation-level Python and native-extension memory profiling.
The existing Gunz `/proc` profiler answers whole-process-tree resource
questions; Memray answers allocation-stack questions. These are complementary.

A Gunz adapter should launch Memray, retain its binary capture, optionally ask
Memray to generate table/flamegraph artifacts, and attach those artifacts to a
single `PerformanceRun`.

### py-spy and Scalene

Use py-spy for low-overhead external Python stack sampling, especially when
attaching to a running process or generating speedscope/flamegraph artifacts.

Use Scalene when Python/native attribution and line-oriented Python CPU/memory
analysis are more useful than generic process-level measurements.

Gunz should normalize only stable summary information and otherwise preserve
their native reports as linked artifacts.

### heaptrack

Use heaptrack for native C/C++ heap allocation analysis. Do not attempt to
implement allocator interception in Python. Gunz should launch it, associate
its output with the measured command/commit, and expose the artifact from the
same report as `perf` and `/proc` measurements.

## What is worth implementing natively

Native implementation is justified when it materially improves integration,
process-tree coverage, portability of the result schema, or measurement
overhead.

### Keep and extend the /proc sampler

This is a Gunz differentiator because it measures the complete live descendant
tree independent of implementation language. Continue implementing:

- per-PID lineage;
- RSS, PSS and private memory;
- user/system CPU;
- instantaneous occupied CPU cores;
- threads/processes;
- page faults/context switches;
- physical storage I/O;
- process start/exit events;
- executable/command identity.

Use batched reads and avoid expensive files such as `smaps_rollup` when the
caller disables detailed memory metrics.

### Fast embedded command timing

Keep a shell-free direct command benchmark mode for programmatic use. Hyperfine
is excellent as a CLI benchmark engine, but spawning another benchmark tool is
unnecessary when a caller needs one tightly integrated measurement with process
sampling.

### Unified result model

Implement a richer `PerformanceRun` rather than forcing every backend into
`BenchmarkResult`:

```text
PerformanceRun
  identity
  environment
  git
  parameters
  timing
  process_tree
  hardware_counters
  allocation_profiles
  stack_profiles
  artifacts
  warnings
```

Backend-specific raw data must remain available; normalization must never throw
away information.

### Derived metrics

Compute inexpensive derived metrics centrally:

- throughput and latency percentiles;
- coefficient of variation;
- CPU cores used;
- CPU efficiency / operation;
- IPC;
- branch/cache miss rates;
- I/O throughput;
- memory-time integral;
- PSS/RSS ratio;
- scaling efficiency for thread/process parameter sweeps.

### Noise and comparability diagnostics

Reuse pyperf for rigorous Python isolation, but implement generic diagnostics
for all backends:

- CPU model mismatch;
- logical CPU-count mismatch;
- kernel/runtime/compiler mismatch;
- dirty working tree;
- thermal/frequency metadata when available;
- background load;
- coefficient of variation/outliers;
- insufficient sample count.

Comparison should warn or refuse when environments are materially
incomparable unless explicitly overridden.

## Performance-oriented implementation choices

For speed, avoid routing every high-frequency sample through Python objects
during capture. The next profiler implementation should support a compact
internal sample representation and convert to dataclasses only at the API or
serialization boundary.

For Linux process discovery, repeatedly scanning all of `/proc` is simple but
becomes expensive on hosts with many processes. Prefer tracking known
descendants and refreshing lineage incrementally. Optional future Linux
backends can investigate pidfds, proc connector/eBPF, or cgroup-based
measurement when the deployment environment supports them.

PSS collection is significantly more expensive than reading `stat` or
`status`. Make it configurable:

```text
memory_detail = "rss" | "pss" | "full"
```

Likewise, allow independent sampling frequencies for cheap CPU/RSS metrics and
expensive detailed-memory metrics.

## Planned adapters

Recommended order:

1. `PyperfBackend` and pyperf JSON ingestion.
2. `HyperfineBackend` and JSON ingestion.
3. derived `perf stat` metrics.
4. unified `PerformanceRun` and artifact registry.
5. Memray launcher/artifact adapter.
6. py-spy launcher/artifact adapter.
7. heaptrack launcher/artifact adapter.
8. Scalene adapter where machine-readable output is sufficiently stable.
9. ASV/pytest-benchmark history ingestion if demanded by consumer repositories.

## Boundary

The project should not become a profiler implementation laboratory. A feature
belongs natively in `gunz-utils` when it provides one or more of:

- cross-language/process-tree visibility;
- substantially lower integration overhead;
- normalized provenance and comparison;
- a shared artifact/report contract;
- a small derived metric that composes existing measurements.

Deep language/runtime/kernel instrumentation should remain delegated to the
specialist tool that already owns it.
