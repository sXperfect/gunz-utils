# Reusable Runtime Adoption Across Gunz Repositories

## Purpose

This document maps repeated infrastructure in sibling repositories to the
shared dependency-free primitives now available on
`feat/reusable-runtime-primitives`.

The goal is not to move domain semantics into gunz-utils. Consumers retain
their schemas, policies, provider taxonomies, and application orchestration
while reusing the underlying mechanism.

## Hyperion

| Current local mechanism | Shared primitive | Consumer-owned behavior |
|---|---|---|
| crawler atomic byte/JSON writes | `gunz_utils.io.atomic_write` / `atomic_json_write` | media validation and crawler manifests |
| `ContentAddressedAssetStore` object placement/rebinding | `gunz_utils.content_store.ContentAddressedStore` | MIME suffix selection and asset records |
| resolver exponential retry loops | `gunz_utils.retry.RetryPolicy` + async runner | host error codes and terminal/no-match rules |
| crawl artifact lineage | `gunz_utils.provenance_graph` | crawler-specific node kinds/metadata |
| cache mirroring | `gunz_utils.sync.rsync_mirror` | CLI/logging/storage policy |

A two-level asset-object layout can use
`ContentAddressedStore(..., fanout_levels=2)`. Downloaded bytes can enter the
store directly through `put_bytes()` / `put_stream()`, and compatibility image
paths can be republished with `materialize(...)` without reimplementing CAS
publication logic.

## Hermes

| Current local mechanism | Shared primitive | Consumer-owned behavior |
|---|---|---|
| fixed retry schedule / Retry-After | `RetryPolicy.delay_override` | FailureClass taxonomy and provider classification |
| recent-vs-historical cache TTL selection | `gunz_utils.cache.RecencyTTLPolicy` | market-specific recency windows and timestamp choice |
| file SHA-256 | `gunz_utils.hashing.file_hash` | dataset entry schema |
| schema/content fingerprints | `structured_hash` | dataframe/schema normalization |
| dataset partition identity | `PartitionManifest` where applicable | trading-calendar semantics |
| run/data provenance | `provenance` + `provenance_graph` | market-data metadata and revisions |

The delay callback can inspect an exception/result and return an exact provider
delay; returning `None` preserves the existing exponential+jitter policy.

## My-Hermes

| Current local mechanism | Shared primitive | Consumer-owned behavior |
|---|---|---|
| 0600 atomic YAML/.env publication | `atomic_write(..., permissions=0o600)` | YAML serialization and secret allowlists |
| asyncio SIGINT/SIGTERM registration | `install_async_signal_handlers` | daemon stop event and shutdown ordering |
| nested config access | existing `deep_get` / `deep_set` | Typer error mapping and validation |
| secret-looking key policy | existing redaction/security utilities | application-specific output/argv policy |

## Helios-JS / Hyperion shared foundation

The earlier `feat/shared-foundation` work remains the base of this branch and
continues to own plugin discovery, schema migration, resource budgets, retry
execution, bounded streaming, resilient atomic I/O, and other mechanism-level
foundation APIs.

## Adoption rules

1. Consumer repositories should depend on a stable gunz-utils revision/release,
   not duplicate source files.
2. Keep compatibility wrappers in consumers when public import paths already
   exist.
3. Do not move domain enums, provider failure categories, crawler schemas,
   trading calendars, ML tensor semantics, or application workflow policy into
   gunz-utils.
4. Prefer namespace imports for new APIs; the package root remains intentionally
   conservative.
5. Migrations should include parity tests demonstrating that shared behavior
   matches the previous local implementation before deleting local code.


## Hyperion / Hermes / My-Hermes lease coordination

All three repositories have durable lease schemas with different domain state,
but share the same worker-liveness mechanism:

- renew ownership periodically while long async work is running;
- stop work immediately if renewal returns false;
- propagate renewal failures rather than leaving orphan workers;
- ensure no heartbeat task survives operation completion.

Use `gunz_utils.leases.run_with_lease_heartbeat` for that mechanism and keep
claim/renew/release persistence in each repository. `LeaseTiming` provides a
shared validation rule that heartbeat cadence must be shorter than the granted
lease duration.
