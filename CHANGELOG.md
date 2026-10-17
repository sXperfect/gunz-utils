# Changelog

All notable changes to **gunz-utils** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Unreleased changes are collected as conflict-free fragments in `changes/`.
Run `python scripts/release.py status` to inspect their release impact.

## [1.17.0] — 2026-10-17

### Added

- Add native C statistical acceleration (`stats.summarize`, `stats.RunningStats.extend`), $O(N \log N)$ 2D Pareto frontier sweep (`stats.pareto_frontier`), stat-based directory tree fingerprinting (`fs.tree_fingerprint`), and harden directory walking against symlink loops (`fs.walk_files`) and file readers against unbounded payloads (`io.read_file_snapshot`).

## [1.16.0] — 2026-10-17

### Added

- Add cross-process advisory file locking (`fs.advisory_file_lock`), optimistic CAS file snapshots (`io.FileSnapshot`, `io.read_file_snapshot`, `io.read_source_file`, `io.physical_lines`), polynomial state-set glob matching (`fs.match_path_glob`, `fs.matches_any_glob`, `fs.walk_files`), online statistics & multi-objective optimization (`stats.RunningStats`, `stats.ecdf`, `stats.pareto_frontier`), and dynamic module loading (`plugins.load_module_from_path`, `plugins.GunzFileFinder`).

## [1.15.0] — 2026-10-17

Unreleased changes are collected as conflict-free fragments in `changes/`. Run `python scripts/release.py status` to inspect them.

### Added

- Consolidate general-purpose utilities into `gunz_utils`:
  - `gunz_utils.io.read_regular_bytes`: TOCTOU-safe regular file reading with `O_NOFOLLOW`, maximum size limits, and pre/post-read stat inode/dev signature verification.
  - `gunz_utils.serialization.decode_json_object` & `load_json_object`: Strict JSON decoding rejecting duplicate dictionary keys, non-finite floats, non-UTF8 encodings, and deeply nested payloads.
  - `gunz_utils.stats`: Summary statistics suite (`SummaryStats`, `percentile`, `median_absolute_deviation`, `mad_outlier_indices`, `summarize`) for robust data summarization and outlier detection.
  - `gunz_utils.formatting`: Terminal presentation utilities (`escape_terminal`, `supports_color`) supporting `NO_COLOR` and `FORCE_COLOR` standards.
- Modernize `scripts/release.py` with multi-repo support (`--root`), dynamic project package discovery, fragment heading injection protection, transactional fragment unlinking rollback, AST version literal scanning, and git-based fragment verification (`check-fragment --base <rev>`).

### Fixed

- Fix `parsing.safe_float` to catch `OverflowError` on extreme integer/exponent values returning `default`, and strictly reject `bool` inputs.
- Refactor `WorkflowDAG` and `ProvenanceGraph` topological ordering, validation, and ancestor traversal to iterative stack algorithms, eliminating `RecursionError` on deep graph structures (>1000 nodes).
- Harden `AsyncRateLimiter` against subnormal positive rates and arithmetic overflow during token deficit calculations and refills.
- Enforce upfront `show_chars` parameter validation in `redact_dict` regardless of whether the dictionary contains matching secret keys.
- Make RLIMIT_STACK configuration cross-platform safe on macOS systems.

- Clean up advisory warnings in `src/gunz_utils`:
  - Use `math.fsum` for exact floating-point summation in `benchmark.metrics`, `benchmark.process`, and `benchmark.runner`.
  - Suppress false-positive advisories with targeted inline directives.
- Implement security input admission and early validation (`INPUT-ADMISSION-2026-10-08`):
  - Enforce bounded reading (`max_bytes=4096`) in `SecureStore._read_private` with both pre-read file size check and post-read byte bounds.
  - Enforce strict salt length validation (`len(salt) == 16`) before constructing `PBKDF2HMAC` in `SecureStore._derive_key`.
  - Validate fixed crypto envelope header lengths in `secure_crypto.decrypt` before unhexing or allocating variable ciphertext payload.
- Execute and verify native macOS Darwin APFS platform contracts (`NP-02` / `GAP-010`), passing all 11 Darwin kernel contract tests and compiling native C extension with Apple clang.
- Update `docs/audits/algorithm-registry.md` resolving `GAP-002` (iterative graph traversal), registering `ALG-080`..`ALG-083`, and synchronizing `scripts/release.py` across sibling repositories (`gunz-style`, `gunz-bench`).

- Fix `tcp_reachable` cumulative timeout tracking across multiple resolved IP addresses to respect the overall timeout deadline.
- Add `max_depth` parameter and recursion depth checking to `deep_merge` to protect against call-stack exhaustion on deeply nested dictionaries.
- Add `max_line_length` guard to `iter_jsonl` to bound memory consumption when reading streaming JSON Lines records.
- Move `# gunz-style: ignore[GS007]` comments to same-line in `project_gitpython.py` and `project_stdlib.py` for AST-based rule suppression.
- Improve numerical stability of backoff saturation calculation in `retry._delay` using ratio logarithm.
- Correct `format_duration(0)` docstring example in `formatting.py` to match `'0ms'` return value.
- Enable file descriptor leak testing on macOS/BSD via `/dev/fd` in `test_resource_lifetime_audit.py`.
- Harden `BaseStrEnum` and `BaseIntEnum` fuzzy lookup and `get_or_none` to reject non-string/boolean inputs cleanly and normalize alias and member-name separators consistently.
- Harden `rsync_mirror` and `process_map`/`process_imap` argument validation against control characters in `completion_marker`/`extra_args`, bare string `extra_args`, and non-boolean flag parameters.

## [1.14.2] — 2026-10-12

### Security

- Anchor content-store fanout operations to directory descriptors on supported
  POSIX platforms, verify and copy from opened regular-file handles, and retain
  materialization staging files until publication. Reject non-ASCII hexadecimal
  digest spellings. Platforms without descriptor-relative no-follow operations
  require trusted directory trees; same-digest hard-link fallback preserves content
  rather than the inode of a competing publisher.

- Reject URI authority delimiters introduced by IDNA hostname normalization.

- SecureStore now authenticates the current store policy when guarding reads and
  mutations, rejects missing key material for previously initialized stores, and
  can recover a verified pending rotation past a malformed primary key without
  ignoring unsafe-file errors.

- Authenticate SecureStore record-format policy and improve master-key rotation recovery after transaction failures. Trusted pre-envelope stores now require explicit `unlock(allow_legacy=True)` followed by `migrate_records()`; existing strict-envelope stores upgrade automatically.

### Fixed

- Apply asynchronous bounded-capture timeouts to process exit and pipe draining.
  On timeout, cancellation, overflow or reader failure, cancel and join owned
  capture tasks, close capture read ends, and reap the child without waiting for
  foreign pipe writers. Preserve shared output limits and repeated cancellation
  cleanup, including timeout/cancellation for unlimited capture.

- Close atomic-write temporary descriptors when permission or file-wrapper setup fails.

- Close rejected coroutine submissions in bounded concurrency helpers, SingleFlight
  and async TTL caches. Preserve cooperative child cleanup through repeated caller
  cancellation, including descriptor release and initiating error/cancellation signals.

- Publish transactional directories with atomic no-replace OS operations; unsupported platforms or filesystems fail explicitly and clean staging.

- Close rejected lease heartbeat coroutines while preserving operation task cleanup
  and the original task submission failure.

- Complete interrupted SecureStore key-mode publication during authenticated unlock, removing obsolete opposite-mode primary material and preserving later same-mode rotation.

- Preserve Python reference values and depth errors for normalization budgets outside
  the native classifier's C-integer range. Check depth with Python semantics first
  and bound only the native optimization budget, retaining the caller's recursive
  budget, default depth and existing native stack-safety cutoff.

- Bound native JSON fast-path recursion independently of interpreter accounting,
  delegating deeper inputs to the Python reference so expanded nesting limits and
  cyclic objects remain safe on Python 3.11 and 3.12. Preserve Python integer-subclass
  arithmetic and comparison semantics in native varint encoding by delegating those
  subclasses to the reference implementation.

- Fix bounded worker pipeline cleanup after partial task setup failure and propagate
  worker or producer cancellation without leaving consumers waiting indefinitely.

- Apply bounded synchronous command timeouts through output pipe draining and clean
  up reader threads when descendants retain pipes after the direct process exits.
  Release the child and capture pipes when reader construction or startup fails.

- Reject nonfinite sync timeouts before creating directories or removing existing
  completion markers.

- Configure the optional Windows MSVC build with the running CPython import library, matching dynamic runtime and isolated intermediate outputs; add preparation checks and Windows-only native contract tests.

- Handle deeply nested standard structures with iterative traversal, reject inconsistent Result variants and non-finite cleanup timeouts, and preserve direct cleanup cancellation.

- Preserve integer-subclass varint compatibility, make canonical set ordering independent of mapping insertion order, validate process-map inputs before consuming them, and keep directory fingerprints and synchronization metadata consistent on failure.

- Keep computations started before synchronous TTL cache clearing from repopulating invalidated entries, while preserving results for their existing callers.

- Roll back artifact files and newly created run directories when benchmark run-directory publication fails before run.json commits, while preserving pre-existing artifacts and the initiating exception.\n

- Serialize cooperating content-store publishers per fanout directory so hard-link fallback cannot overwrite a concurrent winner between the existence check and atomic replacement; publication locks are symlink-safe and work on POSIX and Windows.\n

- Retain monotonic CPU, I/O, fault, and context-switch counters across observed process lifetimes using PID plus Linux start time, so exited children remain represented and PID reuse cannot merge distinct processes.\n

- Reject mismatched procfs PID namespaces before profiling, preserve non-UTF-8 process names and unknown memory readings, and terminate the owned process group on sampling failure while preserving the original exception.

- Enforce retry budgets after callbacks and at exact deadlines, validate large token requests before float rounding, and reject unrepresentable numeric parameters before work begins.

### Documentation

- Clarify that verified content-store reads may reject a concurrent pathname
  replacement even when the replacement has the same digest. Callers may retry
  after cooperating publication settles; returned paths remain snapshots.

## [1.14.1] — 2026-10-08

### Fixed

- Repair `WorkflowDAG.async_execute()` to execute compensation rollback and drain child tasks on caller or stage cancellation, stage cache writes to prevent compensated outputs from surviving failure, isolate newly executed stages from cached hits during compensation, ensure recursive container isolation in `deep_merge()` even when leaf objects cannot be deepcopied, and avoid float overflow in `VirtualClock.now_ns()` for extreme finite seconds.

- Add startup barrier in `WorkflowDAG.async_execute()` to prevent eager execution race conditions during sibling cancellation, ensure uninterruptible completion of compensation rollback under repeated cancellations, make cache publication transactional with rollback on publication failure, add identity-based memoization to `deep_merge()` container isolation to preserve self-referential cycles and avoid exponential DAG expansion, and independently test Python varint decoder by disabling `_accel_decode`.

- Fix regression counting in `scripts/bench.py`, repair async test execution in `test_chaos_fault_injection.py`, guard optional `pydantic` import in `test_models.py`, restore keyword argument parity and test fresh fallback imports in `encode_uvarint`, tighten parameter and finiteness validation across chaos primitives (`VirtualClock`, `FaultyStream`, `AwaitBoundaryChaos`), enforce prompt sibling task cancellation on failure in `WorkflowDAG.async_execute`, reject non-finite floats in pure-Python `to_jsonable()` for native parity with documented identity contracts, isolate subtrees against caller mutation in `deep_merge()`, and handle compiler-launch errors gracefully in `scripts/build_native.py`.

- Repair type parameter handling in `top_k` to ensure cross-version compatibility between mypy 1.19.1 and mypy 2.x without triggering unused-ignore warnings.

- Fix async cache task retention leak when all callers cancel by delegating in-flight cleanup and publication to the producer coroutine, implement descriptor method binding on `_TTLCache` and `_AsyncTTLCache` for instance, class, and static methods across decorator orders, handle overlapping cyclic mappings and recursive tuple back-references in `deep_merge()`, trigger graceful-shutdown cleanup callbacks on task cancellation in `GracefulShutdown.__aexit__()`, ensure write-then-raise cache publication failures purge uncommitted entries in `WorkflowDAG`, and bound asynchronous compensation rollback with an explicit timeout deadline.

- Prevent asynchronous DAG compensation loops from continuing or hanging after rollback timeout cancellation, report skipped stages as cancelled, bound rollback task join in `WorkflowDAG._safe_rollback_async()`, reject non-finite `rollback_timeout` values (`NaN`, `inf`), cancel and drain child tasks on DAG setup failures before unblocking execution, and retain active tasks in `concurrency.map_unordered()` so completed sibling exceptions and early exit cancellations are safely observed without unretrieved-exception warnings.

- Default bucket capacity in `AsyncRateLimiter` to `max(1.0, float(rate))` when capacity is omitted so fractional rates permit default acquisition, enforce acquisition timeouts upon wakeup before deducting token balances, and recheck retry policy deadlines after sleep and retry hooks to prevent starting subsequent attempts after deadline expiration in `run_with_retry()`, `async_run_with_retry()`, `retry()`, and `async_retry()`.

- Bound rollback task join in `WorkflowDAG._safe_rollback_async()` using an explicit deadline to prevent cancellation-suppressing compensators from hanging rollback indefinitely and report unfinished tasks, close un-owned coroutines when stage task creation fails in `WorkflowDAG.async_execute()`, ensure `AsyncCircuitBreaker` clears the half-open probe in-flight flag in a `finally` block even when failure predicates raise while preserving chained causes, and capture event-loop task exception reports in concurrency tests.

- Coordinate `SecureStore` key rotation with inter-process file locks, immediate transactions, and key generation verification (`A12-SS-01`).
- Require `allow_mode_switch=True` during `SecureStore.rotate_master_key()` to prevent unintended passphrase downgrade or conversion (`A12-SS-02`).
- Bind record name and ACL to Fernet ciphertexts using authenticated record envelopes, preventing ciphertext substitution or ACL tampering (`A12-SS-03`).

- Record explicit compensation errors when synchronous rollback encounters asynchronous compensation callbacks in `WorkflowDAG._rollback_sync()`, track generation epochs in `AsyncCircuitBreaker` so in-flight requests admitted before a failure cannot close an open circuit and bypass cooldown recovery, and validate size types transactionally in `ByteReader.read()` before advancing offsets.

- Coordinate `SecureStore.unlock()` candidate selection, verification, initialization, and recovery under `_coordination_lock` to eliminate rotation-recovery races (`A13-SS-01`).
- Ensure exception-safe `_ReentrantFileLock.acquire()` and `release()` descriptor and thread-lock cleanup (`A13-LOCK-01`).
- Add platform-conditional file locking on Windows via `msvcrt.locking` (`A13-PORT-01`).
- Enforce strict envelope verification with explicit `migrate_records()` and `record_format` persistence (`A13-ENV-01`).
- Reject missing or malformed key generation metadata with fail-closed behavior (`A13-GEN-01`).

- Roll back or reconnect SQLite database on transaction commit failures in `SecureStore._transaction_locked()` to prevent uncommitted transaction state poisoning subsequent writes, and authenticate existing record envelopes in `set()` and `delete()` before trusting ACL metadata to prevent unauthorized mutations against tampered database records.

- **`gunz_utils.enums` / `gunz_utils.models`** — added explicit `__all__`
  (consistency with the rest of the package's public modules). `enums` now
  exports `BaseStrEnum`, `OptionalBaseStrEnum`, `BaseIntEnum`, and
  `DEFAULT_MAX_INPUT_LENGTH`; `models` exports `GunzBaseModel`.

## [1.14.0] — 2026-10-02

### Added

- Add `VirtualClock`, `FaultyStream`, and `AwaitBoundaryChaos` testing primitives to `gunz_utils.faults` for testing adversarial I/O errors and cooperative cancellation.
- Accelerate canonical JSON serialization and fingerprinting in `gunz_utils.serialization` and batch streaming in `gunz_utils.streaming`.

### Performance

- Add optional C native extension (`gunz_utils._accel`) for 64-bit unsigned varint encoding and zero-copy decoding in `gunz_utils.binary`, unlocking a ~5x speedup with transparent pure-Python reference fallback.

## [1.13.0] — 2026-10-01

### Added

- Add clean-room property test generators (fuzz_floats, fuzz_strings, fuzz_bytes, fuzz_primitives, fuzz_json_objects) and check_property assertion runner in gunz_utils.testkit.

- Add agent and worker orchestration primitives: ResourceBudget step tracking, concurrent async WorkflowDAG execution with transactional rollback, and GracefulShutdown coordinator.

### Deprecated

- Deprecate gunz_utils.benchmark in favor of standalone gunz-bench package.

### Documentation

- Document cross-project reusable runtime adoption blueprints, architectural definitions, and behavioural specifications.

- Document architectural handoff and stage 30 benchmark modules to gunz-bench/tmp/handsoff/.

- Add native acceleration architecture design, definition, and specification for low-overhead telemetry and vectorized statistics.

## [1.12.0] — 2026-09-29

### Security

- Pin GitHub Actions to immutable current release SHAs and add a repository contract preventing mutable action references from returning.

- Redact raw GitPython and stdlib argument-binding exception messages so arbitrary secret-bearing error text is not copied into public diagnostics.

- Stop embedding raw benchmark-worker stderr in raised exception messages, preventing child-process secrets from leaking through ordinary diagnostics.

- Fail closed on unauthenticated plaintext decryption and disable the predictable hostname/user-derived system passphrase helper; legacy plaintext migration now requires an explicit opt-in.

- Finish the deep audit by binding benchmark artifact copies to opened files, cleaning up POSIX subprocess descendant groups, and raising pytest to 9.0.3 for CVE-2025-71176.

- Make raw exception diagnostics opt-in and stop `CommandError` from echoing subprocess arguments that may contain credentials.

- Raise the optional Matplotlib floor to 3.10.9 so the plotting extra includes the security backport restricting `axes.prop_cycle` expression evaluation.

- Prevent optional logging path/format injection and redact custom Pydantic validator messages that could echo secret-bearing inputs.

- Redact rejected strict-boolean values and enforce finite/integer resource controls for process sampling and bounded streaming helpers.

- Raise the Pydantic optional-dependency floor to 2.4.0 so validation extras cannot resolve versions affected by CVE-2024-3772 (regular-expression denial of service).

### Added

- Publish a PEP 561 `py.typed` marker and complete public namespace API-reference coverage for downstream users and type checkers.

### Fixed

- Harden numerical, timing, serialization, parsing, project-discovery, and benchmark/profiling edge cases, with a maintained algorithm proof guide and audit registry.
- Add method-audit design documentation, exhaustive graph/varint proof tests, and a single-job aggregate CI verifier that reports independent failures together.
- Audit and harden the initial A0 backlog, including path symlink handling, strict formatting/identifier/config/network domains, bounded benchmark-result loading, artifact symlink rejection, perf/worker validation, and executed cross-version proof tests.
- Harden former A1 families: lease/concurrency setup cleanup, strict JSONL, partition boundaries, recursive stdlib type validation, SecureStore audit-atomic transactions, content-store fanout symlink protection, and filesystem no-overwrite failure paths.
- Verify the former A1 algorithm families with 943 passing tests on Python 3.11 and 3.12 plus lint, typing, docs, and packaging/isolation gates.
- Compose the algorithm audit with the newer security-hardened main implementation and verify the combined tree across lint, typing, docs, packaging, and Python 3.11/3.12 tests.

- Enable Google-style Napoleon parsing so expanded API documentation builds correctly for existing public docstrings.

### Documentation

- Remove the obsolete top-level `guides/` tree and establish a tool-neutral `AGENTS.md` covering CI, versioning, security audit, API, testing, and repository-hygiene rules.

- Document the complete 97-file deep security audit, repeatable methodology, confirmed remediations, dependency advisory review, and residual trust boundaries.

- Refresh README installation and feature documentation, add contributor guidance, and remove obsolete tool-generated repository metadata.

- Add a private vulnerability-reporting policy, richer package metadata, current release-history guidance, and maintainable task-archive navigation.

## [1.11.0] — 2026-09-28

### Added

- `gunz_utils.sampling`: deterministic process-independent named-item sampling.
- `gunz_utils.experiments`: pristine-state variant matrices, numeric comparisons, and directional metric-improvement evidence.
- `gunz_utils.structures.deep_diff` and `retain_priority_and_recent`: typed structural comparison and bounded priority retention.
- `gunz_utils.instrumentation.Trace`: lightweight success/failure span tracing.
- Structured and directory hashing extensions plus symlink-safe rooted directory manifests.
- `gunz_utils.content_store`: content-addressed local file storage with integrity verification, configurable digest fanout, and atomic hardlink/copy materialization.
- Named lifecycle fault injection plus reversible process and asyncio termination/preemption signal helpers.
- Rich execution manifests layered on existing runtime provenance.
- Safe authority URI construction and TCP reachability helpers.
- Seeded bootstrap mean confidence intervals and paired standardized-effect summaries.
- Immutable disjoint partition manifests with stable fingerprints plus generic overlap/disjointness checks.
- Generic name allow/deny access policy.
- Fingerprint-aware workflow DAG execution with transitive dependency cache invalidation.
- Context-aware retry delay overrides for provider Retry-After values and fixed schedules in sync/async retry execution.
- `gunz_utils.cache.RecencyTTLPolicy` for timezone-aware recent/historical/empty-result TTL selection without domain-specific market semantics.
- Context-aware retry delay overrides for provider Retry-After values and fixed schedules while preserving exponential/jitter defaults.
- Atomic writes can apply explicit file permissions before content publication.
- Immutable provenance graph nodes with acyclic lineage traversal and unresolved-input reporting.
- Shell-free rsync directory mirroring with advisory coordination and atomic completion markers.
- Backend-neutral renewable lease heartbeat execution that cancels stale work on ownership loss.

- Add stdlib-only release tooling with changelog fragments, semantic-version bump validation, release preparation, and release-readiness checks.

### Changed

- Consolidate hosted verification into one fail-fast runner, with Actions triggered only by pushes to `main` and pull requests targeting `main`; feature-branch pushes no longer consume hosted CI.

- Centralize runtime package-version resolution while preserving historical module-level `__version__` attributes as aliases of the installed distribution version.

### Fixed

- Removed duplicated validation branches in secret redaction.
- Directory fingerprints exclude symlinked files so rooted manifests do not silently depend on external content.
- Deterministic named sampling rejects duplicate names rather than depending on input ordering.
- Rsync cache synchronization now holds its advisory lock through completion-marker publication, preventing false-complete races between concurrent sync processes.
- Advisory lock files reject symlink redirection and use `O_NOFOLLOW` when available.
- Network URIs validate IPv6 authorities, normalize IDNA hostnames, and reject authority-injection delimiters.
- Partition manifests reject scalar strings as identifier collections and defensively freeze assignments.
- Execution manifests normalize run IDs and reject boolean/non-positive attempt counters.
- Paired standardized effects use `None` when mathematically undefined so results remain canonical-JSON compatible.
- Variant experiment failures retain exception type only, avoiding arbitrary secret-bearing exception text in reports.
- Content-addressed ingest now hashes while copying in one pass and rejects symlinked source/store entries.
- Paired-effect helpers use `None` for undefined standardized effects, keeping results compatible with canonical JSON.
- Rsync mirroring rejects hidden destructive extra flags and lock/marker filename collisions.
- Provenance metadata freezing rejects cyclic container graphs explicitly.

### Documentation

- Update repository maintainer metadata to use `yeremiag@gmail.com` consistently.

## [1.10.0] — 2026-09-27

Shared-foundation release for cross-project consumers such as Hyperion and Helios-JS.

### Added

- `gunz_utils.plugins`: deterministic, failure-isolated Python entry-point discovery.
- `gunz_utils.provenance`: allowlisted runtime provenance capture for reproducible artifacts.
- `gunz_utils.versioning`: versioned envelopes and explicit forward schema migration registry.
- `gunz_utils.limits.ResourceBudget`: cumulative byte/item/depth/deadline accounting.
- `gunz_utils.retry.RetryPolicy`, `run_with_retry`, and `async_run_with_retry` for exception- and result-aware retries.
- `gunz_utils.streaming.BoundedWriter`, `DigestWriter`, and `copy_and_hash` for bounded streaming integrity.
- `gunz_utils.io.atomic_json_write` for deterministic crash-safe JSON publication.

### Fixed

- Removed duplicate `lexical_contained_path` and stray duplicated module text from `fs.py`.
- Repaired the stray duplicate `AsyncBulkhead.run` body and unified timeout-aware permit acquisition.
- Restored root exports promised by `gunz_utils.__all__` for context, deprecation, and fault helpers.
- Durable binary `atomic_write` now flushes and fsyncs before atomic replacement.
- Bounded concurrency now propagates child cancellation even when `return_exceptions=True`; cancellation, process-exit, and keyboard-interrupt signals are never converted into ordinary result values.

### Compatibility

- Core remains standard-library only.
- New shared-foundation APIs are namespace-first and are not bulk-exported from the package root.

## [1.8.0] — 2026-08-06

Minor release. Three new utility modules added. **All backward-compatible**
additive changes — no existing API modified or removed.

### Added

- **`gunz_utils.content_hash(data, *, algo="sha256")`** + **`gunz_utils.file_hash(path, *, algo="sha256", chunk_size=65536)`** + **`gunz_utils.short_hash(data, *, chars=8, algo="sha256")`** in `src/gunz_utils/hashing.py` — content-addressing and file-integrity helpers. `content_hash` accepts bytes or UTF-8 strings and returns the lowercase hex digest. `file_hash` streams the file in 64 KiB chunks so memory stays bounded for multi-GB inputs. `short_hash` returns the first `chars` hex characters (git-style fingerprint). Algorithm selection is restricted to a curated `SUPPORTED_ALGOS` frozenset (`sha256`, `sha512`, `sha1`, `blake2b`, `blake2s`, `sha3_256`, `md5`) for predictable cross-platform behavior. `DEFAULT_ALGO`, `DEFAULT_CHUNK_SIZE`, and `SUPPORTED_ALGOS` are also exported for callers that want to introspect or branch on them. No external dependencies — stdlib `hashlib` + `pathlib`.

- **`gunz_utils.deep_get(d, path, *, default=_MISSING, separator=".")`** + **`gunz_utils.deep_set(d, path, value, *, separator=".")`** + **`gunz_utils.deep_merge(base, override, *, list_strategy="replace")`** in `src/gunz_utils/dict_utils.py` — nested-mapping helpers that fill the stdlib gap between raw dict access and a full Pydantic model. `deep_get` traverses via dotted-path string (`"a.b.c"`) or sequence (`["a", "b", "c"]`) and returns `default` for missing keys or scalar traversal failures (silently `None` rather than `KeyError`; pass `default` explicitly to control). `deep_set` creates intermediate dicts and replaces non-dict intermediates with a fresh dict (documented footgun). `deep_merge` returns a new dict (no mutation of either input), recurses into nested dicts, and supports three `list_strategy` modes for list-on-list collisions: `"replace"` (override wins, default), `"concat"` (base + override), and `"dedup"` (concatenated, deduplicated, order preserved). No external dependencies.

- **`gunz_utils.chunked(iterable, n)`** + **`gunz_utils.batched(iterable, n)`** + **`gunz_utils.flatten(nested, *, max_depth=None, types=(list, tuple))`** + **`gunz_utils.first(iterable, *, default=None)`** in `src/gunz_utils/iteration.py` — lazy iteration helpers. `chunked` yields `n`-sized tuples (immutable, hashable, can be `dict` keys / `set` elements); `batched` yields `n`-sized lists (mutable). Both reject non-positive `n`. `flatten` walks a nested iterable and yields each leaf, descending into containers matching `types`. `max_depth` follows Lodash semantics: `None` flattens all levels, `N` flattens `N` levels (nested containers at deeper levels are yielded as leaves). Scalars passed as `nested` are yielded as a single leaf (defensive, despite the `Iterable` type signature). `first` returns the first item or `default` (matching `more_itertools.first`); empty input without an explicit `default` returns `None`. All four are pure generators — no external dependencies.

### Tests

- Added **124 new tests** across 3 test files (`test_hashing.py`, `test_dict_utils.py`, `test_iteration.py`).
- Total test count: 206 → **330** (+124).
- All new tests use `unittest.TestCase` style matching the existing repo convention.

## [1.7.0] — 2026-07-16

Minor release. Five new utility modules added. **All backward-compatible**
additive changes — no existing API modified or removed.

### Added

- **`gunz_utils.atomic_write(path, content, *, mode="w", encoding=None, mkdir=False)`** in `src/gunz_utils/io.py` — crash-safe file write via temp-file + `os.replace()`. Solves the "partial write on crash / disk full" problem that every "save config / save JSON / dump data" path has. Accepts text or binary content, creates parent dirs on demand, cleans up temp file on failure. No external dependencies.
- **`gunz_utils.safe_int`, `safe_float`, `safe_bool`** in `src/gunz_utils/parsing.py` — robust string→primitive parsers with `default=` parameter. `safe_int("3.14")` returns the default (not a coercion error); `safe_int("  42  ")` strips whitespace; `safe_int(value, min=0, max=100)` enforces bounds. Designed for CLI args and config files where coercion failures should fall back gracefully.
- **`gunz_utils.parse_bool(value)`** in `src/gunz_utils/parsing.py` — strict bool parser. Recognizes canonical forms (`true/false`, `1/0`, `yes/no`, `on/off`, etc., case-insensitive) and raises `ValueError` on unrecognized. Pairs with `safe_bool` for use cases where ambiguity must be rejected loudly.
- **`gunz_utils.format_bytes(n, *, precision=1, binary=False)`** in `src/gunz_utils/formatting.py` — human-readable file sizes. SI units by default (`KB = 1000 B`), IEC units with `binary=True` (`KiB = 1024 B`). Up to `TB`/`TiB`.
- **`gunz_utils.format_duration(seconds, *, precision=1)`** in `src/gunz_utils/formatting.py` — human-readable elapsed time. Adaptive precision: `ms` for sub-second, `Xs` for under a minute, `Xm Ys` for under an hour, `Xh Ym Zs` for under a day, `Xd Yh Zm Ws` for longer.
- **`gunz_utils.format_count(n, *, precision=1)`** in `src/gunz_utils/formatting.py` — human-readable large counts with K/M/B/T suffixes. `1000 → 1.0K`, `1_500_000 → 1.5M`, `1_234_567_890 → 1.2B`.
- **`gunz_utils.Timer(label=None, *, auto_start=True)`** + **`gunz_utils.timer(label=None)`** in `src/gunz_utils/timing.py` — context manager for measuring elapsed wall-clock time. Uses `time.perf_counter()` for high precision. Auto-starts (optional), auto-stops on `__exit__`, supports manual `start()`/`stop()`/`elapsed`. The `timer()` convenience function is a `@contextlib.contextmanager` shortcut.
- **`gunz_utils.redact(value, *, show_chars=2)`** + **`gunz_utils.redact_dict(d, *, patterns=None, show_chars=2)`** + **`gunz_utils.SECRET_PATTERNS`** in `src/gunz_utils/redaction.py` — secret masking for logs/dumps/error messages. `redact("hunter2")` → `"h****2"`. `redact_dict(config)` walks a dict (recursively into nested dicts and lists) and masks values whose keys match common secret patterns (`password`, `token`, `api_key`, etc., case-insensitive substring match). Prevents accidental token leakage.

### Tests

- Added **110 new tests** across 5 test files (`test_io.py`, `test_parsing.py`, `test_formatting.py`, `test_timing.py`, `test_redaction.py`).
- Total test count: 96 → **206** (+110).
- All new tests use `unittest.TestCase` style matching the existing repo convention.

## [1.6.0] — 2026-07-16

### Removed

- `gunz_utils.HealthStatus` (MCP server health-check response
  model). The class was added in v1.3.0 as part of the public
  API but was never used internally and is too domain-specific
  for a foundational utilities library. Downstream consumers
  that need this functionality should define their own
  response model:

```python
# Before (v1.5.x and earlier)
from gunz_utils import HealthStatus

# After (v1.6.0+) — define in your own codebase
from pydantic import BaseModel
class HealthStatus(BaseModel):
    status: str = "UNKNOWN"
    # ... your fields here
```

## [1.5.0] — 2026-07-16

### Changed

- Two callers migrated from the `gunz_utils.validation` compat shim
  to the canonical `gunz_utils.ext.validation_pydantic` path:
  - `tests/test_validation_leak.py` (line 2)
  - `docs/source/quickstart.md` (line 37)
- `docs/_build/` Sphinx build artifacts no longer tracked in git.
  87 files that were committed in `82d78df` are now untracked.
  The `.gitignore` line `docs/_build/` was already correct; only the
  pre-existing tracked state needed cleanup. Local builds still
  produce artifacts in `docs/_build/` (gitignored) as before.

### Removed

- **`src/gunz_utils/validation.py`** — backwards-compat shim originally
  added in v1.3.0 (commit `59ec712`) to preserve the historical
  `from gunz_utils.validation import ...` import path during the
  ext.* split. Now dead code (all callers migrated). **Breaking
  change** for external consumers still using the legacy path —
  migrate to `from gunz_utils.ext.validation_pydantic import ...`
  or `from gunz_utils import type_checked, validate_call` (the
  latter works via the `_LAZY` dict in `__init__.py`).

## [1.4.0] — 2026-07-16

### Added

- `GunzBaseModel` — shared Pydantic v2 base class in
  `src/gunz_utils/models.py`. Encapsulates the strictness defaults
  that every HyperHedron domain model should inherit:
  `extra="forbid"`, `str_strip_whitespace=True`,
  `validate_assignment=True`. Re-exported as
  `from gunz_utils import GunzBaseModel` and added to `__all__`.
- `tests/test_core/test_models.py` — 16 unit tests covering
  `GunzBaseModel` configuration, behavior, subclass override, and
  the public API re-export. Test count: 81 → 97.

### Fixed

- `HealthStatus()` no-arg construction now succeeds; the `status`
  field defaults to `"UNKNOWN"` (a sentinel for "not yet checked")
  instead of raising `ValidationError`. Two regression tests added
  to pin the new behavior. Test count: 97 → 99.
- Six `except` clauses now chain their raised exceptions with
  `from exc` (B904). Catches were previously unnamed or lacked the
  explicit `from` clause, which suppressed the original cause.
- Ruff auto-fix pass on 39 issues: unsorted imports (19), blank
  lines with trailing whitespace (11), missing newlines at end of
  file (5), `setattr` with constant (4).

### Changed

- Python v6.0 compliance sweep: 13 modules now have the full
  dunder block (`__author__`, `__email__`, `__license__`,
  `__version__ = "1.4.0"`); 3 files had `# -*- coding: utf-8 -*-`
  removed; 4 files had `t.Optional` / `typing.Optional` /
  `typing.Dict` replaced with modern `X | None` / `dict[str, Any]`
  syntax.
- Ruff line-length enforcement is now satisfied:
  `ruff check src/ tests/` reports 0 issues across the codebase.
  36 line-too-long (E501) violations were fixed via line wrapping
  and implicit string concatenation.

### Removed

- **CI**: `deploy_docs.yml` no longer uploads to Cloudflare
  Pages (the step was removed entirely). Both `ci.yml` and
  `deploy_docs.yml` triggers are pinned to the sentinel branch
  `never`, so GitHub Actions no longer runs on push or pull
  request. Local CI via [`act`](https://github.com/nektos/act)
  remains the supported workflow.

## [1.3.2] — 2026-07-16

### Changed

- Documentation build pipeline aligned with `pyproject.toml`. The
  `docs` extra now declares `sphinx_rtd_theme` (matching `conf.py`)
  and no longer declares `furo`. Workflow installs `.[docs]`
  instead of `.[all]`, so CI can actually build the docs.
- `conf.py` `release` bumped to `1.3.0` (was stale at `1.1.0`).

### Added

- Compat shim at `src/gunz_utils/validation.py` re-exporting
  `type_checked` and `validate_call` from `ext.validation_pydantic`.
  Preserves the historical `from gunz_utils.validation import …`
  import path for callers that have not yet migrated to the v1.3.0
  `ext.*` layout.
- `[tool.ruff]` configuration in `pyproject.toml` (line-length 88,
  Pyflakes + pycodestyle + bugbear + isort + pyupgrade).

### Fixed

- `tests/test_project.py` (legacy 53-line flat test) collided with
  the new `tests/test_project/` package on the same module name,
  causing pytest to abort collection. The legacy file is removed;
  `tests/test_project/test_project.py` covers the same 6 scenarios.
- Four test files had redundant `# -*- coding: utf-8 -*-` headers
  stripped (`test_security_reserved.py`, `test_enums_security.py`,
  and the same pair under `tests/test_core/`).

### Removed

- Three dead-duplicate root-level source files left over from the
  v1.3.0 `ext.*` split: `src/gunz_utils/secure_store.py`,
  `src/gunz_utils/crypto.py`, `src/gunz_utils/logging.py`. None
  were reachable through the public package surface
  (lazy-import shim in `__init__.py` only exposes `ext.*` paths).
- Cloudflare Pages deploy step from the `deploy_docs` workflow.
  The CI now builds the docs to verify the build works, but does
  not upload them. `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`
  are no longer consumed by any workflow.

## [1.3.1] — 2026-07-08

### Fixed

- `gunz_utils.__version__` reported `"1.1.0"` from a v1.3.0 install.
  Synced to `"1.3.0"` to match `pyproject.toml` and the v1.3.0 tag.

### Removed

- Four stale `__version__ = "1.0.0"` duplicates from `enums.py`,
  `security.py`, `ext.validation_pydantic`, and `ext.project_gitpython`.
  `__init__.py` is the canonical source now.

## [1.3.0] — 2026-06-29

### Added

- `loguru>=0.7.0` is now a declared runtime dependency, matching its
  two import sites (`gunz_utils.project`, `gunz_utils.logging`).
- `[project.optional-dependencies]` groups: `validation`,
  `project`, `observability`, `secure`, `all`, plus the existing
  `docs` group. Allows narrower installs of the heavy bundles.
- `[dependency-groups]` (PEP 735): `dev`, `test`, `lint` for dev/CI.
- New module `gunz_utils.ext.*` for explicit backend selection:
  - `ext.validation_pydantic` — `type_checked` (pydantic backend,
    default).
  - `ext.validation_stdlib`   — `type_checked` (stdlib fallback).
  - `ext.project_gitpython`   — `resolve_project_root` (gitpython +
    loguru, default).
  - `ext.project_stdlib`      — `resolve_project_root` (stdlib path
    walk + git rev-parse fallback).
  - `ext.observability_loguru`, `ext.observability_stdlib`,
    `ext.secure_crypto`, `ext.secure_store`.
- `gunz_utils.__init__` re-exports `UpstreamClient`, `BaseUpstream`,
  and the four `UpstreamError` subclasses from the new
  `upstream_protocol` module.

### Fixed

- `__init__.py` was previously frozen at `__version__ = "1.0.0"` and
  did not re-export the post-v1.0.0 modules. Both corrected.

## [1.1.0] — 2026-06-29

Added `gunz_utils.crypto`, `gunz_utils.logging`, `gunz_utils.models`,
`gunz_utils.secure_store`, `gunz_utils.upstream_protocol` and the
`cryptography>=42.0.0`, `gitpython>=3.1.0` runtime deps.

## [1.0.0] — 2026-06-29

Initial BSD-3 release with `BaseStrEnum`, `BaseIntEnum`,
`OptionalBaseStrEnum`, `sanitize_filename`, `safe_path_join`,
`type_checked`, `resolve_project_root`.
