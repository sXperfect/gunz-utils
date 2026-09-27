# Quickstart

**Gunz Utils** provides reusable, domain-neutral Python primitives shared across
Gunz projects. The core package has no runtime dependencies.

## Collections and iteration

```python
from gunz_utils import chunked, deep_get

batches = list(chunked(range(5), n=2))
value = deep_get({"job": {"retries": 3}}, "job.retries")
```

## Deterministic hashing and serialization

```python
from gunz_utils import canonical_json, content_hash

payload = {"name": "example", "enabled": True}
encoded = canonical_json(payload)
digest = content_hash(encoded)
```

## Safe paths and redaction

```python
from gunz_utils import redact_dict, safe_path_join

path = safe_path_join("/srv/data", "reports", "latest.json")
safe_log = redact_dict({"user": "alice", "password": "secret"})
```

## Concurrency and retries

```python
from gunz_utils import async_retry, gather_limited

# See the API reference for policies, limits, and error handling.
```

## Optional integrations

Optional dependencies are loaded lazily:

```python
from gunz_utils import SecureStore, resolve_project_root, setup_logging, type_checked
```

Install the corresponding extras before using these symbols. See
[Installation](installation.md) for the extras matrix.

## Benchmarking

```python
from gunz_utils.benchmark import benchmark

result = benchmark(sum, range(10_000), warmup=3, iterations=20)
print(result.stats.mean, result.stats.p95)
```

The benchmark package also provides process profiling, comparison, regression
gates, history, reporting, artifact verification, and optional plotting.

For the complete surface, continue with the [API reference](api.rst) and
[Core concepts](concepts.md).
