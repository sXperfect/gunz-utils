# Gunz Utils

[![CI](https://github.com/sXperfect/gunz-utils/actions/workflows/ci.yml/badge.svg)](https://github.com/sXperfect/gunz-utils/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Clear_BSD-blue.svg)](LICENSE.md)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)

**Gunz Utils** is a general-purpose Python utility library for production environments. It bundles enhanced Enums, dict/iteration helpers, hashing, I/O, redaction, timing, validation, and an MCP-friendly `UpstreamClient` Protocol — all under one zero-dep core with opt-in extras for `pydantic`, `gitpython`, `cryptography`, and `loguru`.

## Features

| Module | What it gives you | Deps |
|:-------|:------------------|:-----|
| [`enums`](src/gunz_utils/enums.py) | `BaseStrEnum`, `BaseIntEnum`, `OptionalBaseStrEnum` — fuzzy lookup, aliases, safe `get_or_none`, DoS-bounded input length | stdlib |
| [`dict_utils`](src/gunz_utils/dict_utils.py) | `deep_get`, `deep_set`, `deep_merge` for nested dicts | stdlib |
| [`formatting`](src/gunz_utils/formatting.py) | `format_bytes`, `format_duration`, `format_count` — human-readable sizes | stdlib |
| [`hashing`](src/gunz_utils/hashing.py) | `content_hash`, `file_hash`, `short_hash` — deterministic content/file digests | stdlib |
| [`io`](src/gunz_utils/io.py) | `atomic_write`, `atomic_json_write` — crash-safe deterministic output | stdlib |
| [`iteration`](src/gunz_utils/iteration.py) | `chunked`, `batched`, `flatten`, `first` — lazy generators | stdlib |
| [`cache`](src/gunz_utils/cache.py) | TTL memoization + async `SingleFlight` request coalescing | stdlib |
| [`concurrency`](src/gunz_utils/concurrency.py) | bounded async gather/map helpers | stdlib |
| [`retry`](src/gunz_utils/retry.py) | result/exception-aware retry with context-specific delay overrides | stdlib |
| [`limits`](src/gunz_utils/limits.py) | stateless `Limits` + cumulative `ResourceBudget` accounting | stdlib |
| [`plugins`](src/gunz_utils/plugins.py) | deterministic failure-isolated entry-point discovery | stdlib |
| [`provenance`](src/gunz_utils/provenance.py) | allowlisted runtime provenance for reproducible artifacts | stdlib |
| [`streaming`](src/gunz_utils/streaming.py) | bounded/digesting writers and copy-and-hash | stdlib |
| [`versioning`](src/gunz_utils/versioning.py) | versioned envelopes and forward schema migrations | stdlib |
| [`sampling`](src/gunz_utils/sampling.py) | deterministic named-item sampling across processes | stdlib |
| [`experiments`](src/gunz_utils/experiments.py) | pristine-state variant matrices and metric comparisons | stdlib |
| [`content_store`](src/gunz_utils/content_store.py) | content-addressed storage, fanout, integrity checks, and atomic materialization | stdlib |
| [`dag`](src/gunz_utils/dag.py) | dependency-ordered workflow execution with fingerprint caching | stdlib |
| [`network`](src/gunz_utils/network.py) | safe network URI construction and TCP reachability checks | stdlib |
| [`partitions`](src/gunz_utils/partitions.py) | immutable disjoint partition manifests with stable fingerprints | stdlib |
| [`stats`](src/gunz_utils/stats.py) | bootstrap mean confidence intervals and paired effects | stdlib |
| [`signals`](src/gunz_utils/signals.py) | reversible process/asyncio termination handlers | stdlib |
| [`provenance_graph`](src/gunz_utils/provenance_graph.py) | immutable provenance nodes and acyclic lineage traversal | stdlib |
| [`sync`](src/gunz_utils/sync.py) | shell-free rsync mirroring with optional shared-filesystem locking | stdlib |
| [`serialization`](src/gunz_utils/serialization.py) | deterministic JSON + common-object normalization | stdlib |
| [`subprocess`](src/gunz_utils/subprocess.py) | structured sync/async shell-free command execution | stdlib |
| [`models`](src/gunz_utils/models.py) | `GunzBaseModel` — `pydantic.BaseModel` configured to forbid extra fields | `validation` extra |
| [`parsing`](src/gunz_utils/parsing.py) | `safe_int`, `safe_float`, `safe_bool`, `parse_bool` — strict coercion with diagnostics | stdlib |
| [`redaction`](src/gunz_utils/redaction.py) | `redact`, `redact_dict` — pattern-based secret scrubbing | stdlib |
| [`security`](src/gunz_utils/security.py) | `sanitize_filename`, `safe_path_join` — path traversal & reserved-name guards | stdlib |
| [`timing`](src/gunz_utils/timing.py) | `Timer` + `timer` context manager — `time.perf_counter` based | stdlib |
| [`upstream_protocol`](src/gunz_utils/upstream_protocol.py) | `UpstreamClient` Protocol + `UpstreamError` hierarchy + `BaseUpstream` | stdlib |
| `type_checked` *(lazy)* | `@type_checked` decorator (Pydantic v2 backend) | `pydantic` extra |
| `resolve_project_root` *(lazy)* | Git-aware repo-root discovery + `sys.path` injection | `gitpython` extra |
| `setup_logging` *(lazy)* | Structured `loguru` logging with rotation | `loguru` extra |
| `SecureStore` / `encrypt` / `decrypt` *(lazy)* | Fernet-backed secret-at-rest store + helpers | `cryptography` extra |

## Quick Start

```python
from gunz_utils import (
    BaseStrEnum, chunked, format_bytes, atomic_write, redact,
    Timer, resolve_project_root,
)
```

### Enums with fuzzy matching

```python
class Color(BaseStrEnum):
    __ALIASES__ = {"crimson": "red"}
    RED = "red"
    DARK_BLUE = "dark_blue"

Color.from_fuzzy_string("dark-blue")  # Color.DARK_BLUE
Color.from_fuzzy_string("crimson")    # Color.RED
Color.get_or_none("purple")           # None
```

### Iteration helpers

```python
list(chunked([1, 2, 3, 4, 5], n=2))   # [(1, 2), (3, 4), (5,)]
list(flatten([[1, [2]], 3, [[4]]]))       # [1, 2, 3, 4]
first([1, 2, 3])                          # 1
```

### Human-readable formatting

```python
format_bytes(1_500_000)     # "1.43 MB"
format_duration(3661)       # "1h 1m 1s"
format_count(1_234_567)     # "1.23M"
```

### Atomic writes + content hashing

```python
from gunz_utils import atomic_write, content_hash

atomic_write("/tmp/report.json", '{"ok": true}')
digest = content_hash(b"hello")  # sha256 hex digest
```

### Redaction

```python
from gunz_utils import redact, redact_dict

redact("api_key=sk-live-abc123")                    # "ap****23"
redact_dict({"user": "alice", "password": "p@ss"})  # {"user": "alice", "password": "****"}
```

### Timing

```python
with Timer("phase-1") as t:
    do_work()
print(t.elapsed)  # seconds
```

### MCP-friendly upstream Protocol

```python
from gunz_utils import UpstreamClient, UpstreamError

class MyUpstream:
    name = "demo"
    async def call(self, tool_name, arguments): ...
    async def health_check(self) -> bool: return True
    async def close(self) -> None: ...

isinstance(MyUpstream(), UpstreamClient)  # True (runtime-checkable Protocol)
```

### Project root discovery

```python
from gunz_utils import resolve_project_root
root = resolve_project_root()
print(f"Project at: {root}")
```

### Production foundation helpers

`gunz_utils` also provides bounded async concurrency, generic retry/backoff, TTL caching with async single-flight, deterministic JSON serialization, structured shell-free subprocess execution, failure-isolated plugin discovery, cumulative resource budgets, reproducibility metadata, schema migration envelopes, and bounded digest streaming. Service-specific idempotency and domain policy remain consumer responsibilities.

## Benchmarking and native profiling

The `gunz_utils.benchmark` package provides a reusable benchmark SDK while each
consumer repository owns its benchmark definitions and baselines.

```python
from gunz_utils.benchmark import benchmark, profile_command

timing = benchmark(encode, payload, warmup=5, iterations=50)

profile = profile_command(
    ["./native-encoder", "input.bin"],
    interval=0.01,
)
print(profile.wall_seconds, profile.peak_rss_bytes)
```

On Linux, `profile_command` samples the root command and all live descendants
through `/proc`, including non-Python executables. Samples record aggregate RSS,
user/system CPU time, physical read/write bytes, process count, and elapsed time.
Because descendants can be short-lived between sampling intervals, use a suitably
small interval for workloads that spawn very short processes.

Plotting is optional:

```bash
pip install "gunz-utils[plot]"
```

```python
from gunz_utils.benchmark import plot_benchmark, plot_process_samples

plot_benchmark(timing).savefig("timing.png")
plot_process_samples(profile, "rss_bytes").savefig("memory.png")
plot_process_samples(profile, "cpu_user_seconds").savefig("cpu.png")
```

Raw samples and metadata should be retained as JSON artifacts so baseline and
candidate runs can be compared reproducibly.

## Installation

```bash
pip install git+https://github.com/sXperfect/gunz-utils.git         # core only
pip install gunz-utils[validation]   # add pydantic + @type_checked
pip install gunz-utils[secure]       # add cryptography + SecureStore
pip install gunz-utils[project]      # add gitpython + resolve_project_root
pip install gunz-utils[observability] # add loguru + setup_logging
pip install gunz-utils[all]          # everything
pip install gunz-utils[docs]         # + sphinx toolchain
```

## Migration

### v1.5.0 — `gunz_utils.validation` shim removed

The backwards-compat shim at `gunz_utils.validation` was removed in v1.5.0.
If you were importing from it directly, migrate to:

```python
# Canonical ext.* module
from gunz_utils.ext.validation_pydantic import type_checked, validate_call

# Or — preferred — the lazy package surface
from gunz_utils import type_checked, validate_call
```

`from gunz_utils import …` keeps working unchanged.

### v1.6.0 — `gunz_utils.logging`, `gunz_utils.crypto` removed

Same story: moved to `ext.observability_loguru` and `ext.secure_crypto`,
both reachable from the package surface (`setup_logging`, `encrypt`,
`decrypt`, etc.).

### Secure storage

```python
from gunz_utils import SecureStore

with SecureStore(library_name="my-app") as store:
    store.unlock(passphrase="use-a-secret-from-your-keyring")
    store.set("service.token", "secret", acl=["cli"])
    token = store.get("service.token", caller="cli")
```

The standalone AES helpers require an explicit passphrase. Legacy hostname-derived
`aes256:` ciphertext is intentionally rejected and must be migrated with a
trusted older client.

## Documentation

```bash
pip install .[docs]
./scripts/build_docs.sh
```

## CI policy

Hosted CI is intentionally narrow to reduce runner usage and duplicate work:

- feature-branch pushes do not run GitHub Actions;
- pushes to `main` run the single sequential `CI / verify` job;
- pull requests run CI only when their base branch is `main`;
- superseded runs for the same PR/ref are cancelled.

The hosted job checks release metadata first, then Ruff, mypy, the Python 3.11
test suite, strict documentation, packaging/isolation, and finally Python 3.12
compatibility. Development branches should use the same local gate before merge.

## Release management

`pyproject.toml` is the sole static source of the package version.
`gunz_utils.__version__` and the Sphinx release string are derived from
installed package metadata. User-visible changes are recorded as conflict-free
files under `changes/` instead of editing the top of `CHANGELOG.md` on every
branch.

```bash
python scripts/release.py check          # validate release metadata
python scripts/release.py status         # inspect pending SemVer impact
python scripts/release.py prepare X.Y.Z  # assemble a release locally
python scripts/release.py verify         # verify prepared release metadata
```

Release commits use `chore(release): vX.Y.Z`. See
[`docs/development/releases.md`](docs/development/releases.md) for the complete
process and
[`docs/development/release-history.md`](docs/development/release-history.md)
for the audited historical tag/version gaps.

## Development

```bash
pip install -e ".[all,plot,docs]"  # editable install with CI-capable extras
./scripts/verify.sh                # release + lint + tests + docs + packaging
```

## License

Clear BSD — see [LICENSE.md](LICENSE.md).

Copyright (c) 2025-present, Yeremia Gunawan Adhisantoso (sXperfect).