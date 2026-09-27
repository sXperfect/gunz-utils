# Gunz Utils

[![CI](https://github.com/sXperfect/gunz-utils/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/sXperfect/gunz-utils/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Clear%20BSD-blue.svg)](LICENSE.md)
[![Core dependencies](https://img.shields.io/badge/core%20dependencies-0-success.svg)](pyproject.toml)

**Gunz Utils** is the shared Python utility foundation for the Gunz ecosystem. It
collects reusable, domain-neutral primitives for configuration, concurrency,
resilience, I/O, security, reproducibility, process execution, experimentation,
and benchmarking.

The core package targets **Python 3.11+** and has **no runtime dependencies**.
Third-party integrations are opt-in extras. Installation below intentionally
uses source/VCS installation rather than assuming a PyPI or GitHub Release.

## Scope

`gunz-utils` is intended for small, reusable building blocks that can be shared
across repositories. Service-specific policy, application schemas, market/data
semantics, and ML-framework-specific behavior should remain in their owning
projects unless a stable cross-project abstraction has emerged.

## Capabilities

| Area | Representative modules |
|---|---|
| Data, configuration, and typing | [`collections`](src/gunz_utils/collections.py), [`dict_utils`](src/gunz_utils/dict_utils.py), [`enums`](src/gunz_utils/enums.py), [`config`](src/gunz_utils/config.py), [`env`](src/gunz_utils/env.py), [`parsing`](src/gunz_utils/parsing.py) |
| Async, caching, and resilience | [`async_utils`](src/gunz_utils/async_utils.py), [`concurrency`](src/gunz_utils/concurrency.py), [`cache`](src/gunz_utils/cache.py), [`retry`](src/gunz_utils/retry.py), [`resilience`](src/gunz_utils/resilience.py), [`rate_limit`](src/gunz_utils/rate_limit.py), [`leases`](src/gunz_utils/leases.py) |
| I/O, hashing, and execution | [`io`](src/gunz_utils/io.py), [`hashing`](src/gunz_utils/hashing.py), [`serialization`](src/gunz_utils/serialization.py), [`streaming`](src/gunz_utils/streaming.py), [`subprocess`](src/gunz_utils/subprocess.py), [`sync`](src/gunz_utils/sync.py), [`content_store`](src/gunz_utils/content_store.py) |
| Security and diagnostics | [`security`](src/gunz_utils/security.py), [`redaction`](src/gunz_utils/redaction.py), [`diagnostics`](src/gunz_utils/diagnostics.py), [`faults`](src/gunz_utils/faults.py), [`signals`](src/gunz_utils/signals.py) |
| Reproducibility and workflows | [`provenance`](src/gunz_utils/provenance.py), [`provenance_graph`](src/gunz_utils/provenance_graph.py), [`versioning`](src/gunz_utils/versioning.py), [`dag`](src/gunz_utils/dag.py), [`partitions`](src/gunz_utils/partitions.py) |
| Experiments and statistics | [`sampling`](src/gunz_utils/sampling.py), [`experiments`](src/gunz_utils/experiments.py), [`structures`](src/gunz_utils/structures.py), [`stats`](src/gunz_utils/stats.py), [`instrumentation`](src/gunz_utils/instrumentation.py) |
| Benchmarking and profiling | [`gunz_utils.benchmark`](src/gunz_utils/benchmark/) |
| Optional integrations | [`gunz_utils.ext`](src/gunz_utils/ext/) |

For the complete public surface, see the
[API reference](docs/source/api.rst) and [`gunz_utils.__init__`](src/gunz_utils/__init__.py).

## Installation

### Install directly from GitHub

Core only:

```bash
python -m pip install "gunz-utils @ git+https://github.com/sXperfect/gunz-utils.git"
```

With the common optional integrations:

```bash
python -m pip install "gunz-utils[all,plot] @ git+https://github.com/sXperfect/gunz-utils.git"
```

### Install from a local checkout

```bash
git clone https://github.com/sXperfect/gunz-utils.git
cd gunz-utils
python -m pip install -e .
```

Available extras are defined in [`pyproject.toml`](pyproject.toml):

| Extra | Adds |
|---|---|
| `validation` | Pydantic-backed validation helpers |
| `project` | GitPython-backed project discovery |
| `observability` | Loguru-backed logging setup |
| `secure` | Cryptography-backed encryption and secure storage |
| `plot` | Matplotlib plotting for benchmark outputs |
| `all` | Runtime integration extras (`validation`, `project`, `observability`, `secure`) |
| `docs` | Sphinx documentation toolchain |

`all` intentionally does not include `plot` or `docs`.

## Quick start

Most frequently used primitives are exported from the package root:

```python
from gunz_utils import (
    chunked,
    content_hash,
    format_bytes,
    redact_dict,
    safe_path_join,
)

batches = list(chunked(range(5), n=2))
digest = content_hash(b"hello")
size = format_bytes(1_500_000)
safe_path = safe_path_join("/srv/data", "reports", "latest.json")
clean = redact_dict({"user": "alice", "password": "secret"})
```

Optional integrations are loaded lazily, so importing `gunz_utils` does not
pull their third-party dependencies into the core package:

```python
from gunz_utils import SecureStore, resolve_project_root, setup_logging, type_checked
```

Install the corresponding extras before using those symbols.

## Benchmarking and profiling

The [`gunz_utils.benchmark`](src/gunz_utils/benchmark/) package provides
reusable benchmark execution, process sampling, comparison, regression policy,
history, artifact verification, reporting, and optional plotting.

```python
from gunz_utils.benchmark import benchmark, profile_command

timing = benchmark(sum, range(10_000), warmup=5, iterations=50)
profile = profile_command(
    ["python", "-c", "print(sum(range(10000)))"],
    interval=0.01,
)

print(timing.stats.mean)
print(profile.wall_seconds, profile.peak_rss_bytes)
```

On Linux, process profiling uses `/proc` and follows live descendants. Portable
fallbacks are available where Linux-specific counters are unavailable.

## Documentation

- [Quick start](docs/source/quickstart.md)
- [Installation guide](docs/source/installation.md)
- [API reference](docs/source/api.rst)
- [Concepts](docs/source/concepts.md)
- [Changelog](CHANGELOG.md)
- [Release process](docs/development/releases.md)
- [Contributing](CONTRIBUTING.md)

Build the documentation locally with:

```bash
python -m pip install -e ".[docs]"
./scripts/build_docs.sh
```

## Development

Install the package plus the same development tools used by hosted CI:

```bash
python -m pip install -e ".[all,plot,docs]"
python -m pip install pytest==9.0.2 ruff==0.14.10 mypy==1.19.1
```

Run the canonical local verification gate:

```bash
./scripts/verify.sh
```

Hosted GitHub Actions intentionally run only for pushes to `main` and pull
requests targeting `main`; feature-branch pushes do not consume hosted CI.

User-visible changes should add a changelog fragment under [`changes/`](changes/)
rather than editing the top of `CHANGELOG.md` directly. See
[`changes/README.md`](changes/README.md) and
[`docs/development/releases.md`](docs/development/releases.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contributor workflow.

## Security

Report suspected vulnerabilities privately using [SECURITY.md](SECURITY.md). Do not open a public issue for an undisclosed security vulnerability.

## License

Clear BSD. See [LICENSE.md](LICENSE.md).

Copyright (c) 2025-present, Yeremia Gunawan Adhisantoso (sXperfect).
