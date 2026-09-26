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
| [`hashing`](src/gunz_utils/hashing.py) | `content_hash`, `file_hash`, `short_hash` — blake2b/sha256, constant-time compare | stdlib |
| [`io`](src/gunz_utils/io.py) | `atomic_write` — crash-safe file writes with `os.replace` | stdlib |
| [`iteration`](src/gunz_utils/iteration.py) | `chunked`, `batched`, `flatten`, `first` — lazy generators | stdlib |
| [`cache`](src/gunz_utils/cache.py) | TTL memoization + async `SingleFlight` request coalescing | stdlib |
| [`concurrency`](src/gunz_utils/concurrency.py) | bounded async gather/map helpers | stdlib |
| [`retry`](src/gunz_utils/retry.py) | sync/async exponential retry with optional jitter | stdlib |
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

atomic_write("/tmp/report.json", b'{"ok": true}')
digest = content_hash(b"hello")  # blake2b hex digest
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

`gunz_utils` also provides bounded async concurrency, generic retry/backoff, TTL caching with async single-flight, deterministic JSON serialization, and structured shell-free subprocess execution. Service-specific idempotency and retry policy remain consumer responsibilities.

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

GitHub Actions does not run automatically for pull requests or feature-branch
pushes. CI runs on pushes to `main` and `develop`, and can be started manually
with `workflow_dispatch`. Development branches should run the test, Ruff, and
mypy commands locally before merge.

## Development

```bash
pip install -e ".[all]"   # editable install with everything
./scripts/verify.sh       # compile + lint + type-check + full tests
```

## License

Clear BSD — see [LICENSE.md](LICENSE.md).

Copyright (c) 2025-present, Yeremia Gunawan Adhisantoso (sXperfect).