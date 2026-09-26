# Security, Reliability, and Performance Hardening

## Scope

This document records the hardening work derived from the September 2026
repository audit. The changes preserve the small utility-library scope while
making security-sensitive behavior explicit and benchmarkable.

## Security invariants

1. Encryption keys must contain secret entropy. Hostnames and usernames are
   identifiers, not key material.
2. Ciphertext formats are versioned. New AES-GCM values use `aes256:v2:`.
3. SecureStore publishes an unlocked key only after authenticating it against
   existing encrypted state.
4. Existing ACLs are preserved unless an authorized caller explicitly changes
   them. Read, overwrite, and delete all enforce ACLs.
5. Key rotation and writes are serialized in-process. Rotation decrypts all
   rows before beginning mutation and performs database changes transactionally.
6. Key/salt files are created with owner-only permissions from the first open.
7. Production logging disables Loguru variable diagnosis.
8. Redaction never reveals content when `show_chars=0` and propagates secret
   context through nested containers.

## Reliability invariants

- `atomic_write(..., durable=True)` fsyncs file data and, on supported POSIX
  platforms, the parent directory after replacement.
- `flatten` rejects cycles and bounds recursive nesting.
- `deep_merge(..., list_strategy="dedup")` uses equality, not raw hash values,
  so hash collisions cannot drop distinct elements.
- Binary secrets use `SecureStore.get_bytes`; `get` is explicitly UTF-8 text.

## Performance

`chunked` and `batched` use `itertools.islice` to move the hot per-item loop
into C. The repeatable microbenchmark is `benchmarks/bench_iteration.py`.
Performance claims must be based on that benchmark or a representative
application workload, not on comments in source.

## Packaging

The default installation is stdlib-only. Pydantic, cryptography, GitPython,
and Loguru are extras and their public package attributes are lazy-loaded.
CI verifies a `pip install . --no-deps` import path.

## Remaining platform boundary

`safe_path_join` validates containment but callers that open attacker-controlled
paths should use `open_path_under_base` where supported. Cross-process
SecureStore coordination remains a consumer-level deployment concern; sharing
one store between unrelated processes requires an external lock or a future
cross-process locking layer.
