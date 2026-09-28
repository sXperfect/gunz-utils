# Deep Security Audit — 2026-09-28

## Executive summary

Branch: `security/deep-audit`

Baseline: `cf3697d7457c5901ee1c927bc6dae347d5428722`

The audit inventoried and mechanically reviewed **97/97 Python source files**
under `src/gunz_utils/`, then manually threat-reviewed security-sensitive
trust boundaries and performed an advisory review of optional dependency floors.

No critical issue was identified. Multiple high- and medium-risk weaknesses
were found and remediated on the audit branch. These include permissive
dependency floors, path/symlink races, ineffective subprocess output limits,
rsync execution-option injection, secure-store filesystem trust, weak
content-addressing algorithms, secret-bearing diagnostics, resource-control
edge cases, cryptographic downgrade behavior, and mutable CI action references.

This report does **not** assert that the project is vulnerability-free. It
records what was reviewed, what was fixed, and what remains a documented trust
boundary.

## Coverage

### Complete mechanical coverage

All 97 package Python files were parsed and inspected for dangerous execution,
deserialization, subprocess, filesystem, network, cryptographic, environment,
dynamic-import, regex, exception, and runtime-assert patterns.

The branch adds `tests/test_core/test_security_static_contracts.py` so several
of these invariants become permanent regression checks.

### Manual threat review

Manual review concentrated on:

- `security.py`, `fs.py`, `io.py`, `content_store.py`, `hashing.py`;
- `subprocess.py`, `sync.py`, benchmark process/worker/I/O/artifact helpers;
- `network.py`, `serialization.py`, `streaming.py`;
- `redaction.py`, `diagnostics.py`, observability and validation backends;
- `ext/secure_crypto.py`, `ext/secure_store.py`;
- project-root GitPython/stdlib backends;
- plugins and provenance capture;
- cache, limits, retry, rate limiting, resilience, upstream policy and leases;
- CI workflow supply-chain references.

## Confirmed findings and remediation

| ID | Risk | Area | Finding | Remediation |
|---|---|---|---|---|
| SA-01 | High | dependencies | Optional floors admitted releases with reviewed security advisories. | Raised Pydantic to >=2.4.0, GitPython to >=3.1.62, Cryptography to >=50.0.1 and Matplotlib to >=3.10.9; added contract tests. |
| SA-02 | High | subprocess | `max_output_bytes` was checked after complete stdout/stderr buffering, so a noisy child could exhaust memory first; descendants could also keep capture pipes alive after the direct child exited. | Sync/async bounded capture now streams into capped buffers and POSIX bounded/async cleanup uses isolated process groups. |
| SA-03 | High | filesystem | `open_path_under_base` protected only the final component; intermediate directory replacement could race the open. | POSIX path walk now uses directory FDs plus `O_DIRECTORY|O_NOFOLLOW` for each component and `fstat` for the final regular file. |
| SA-04 | High | rsync | `extra_args` admitted execution-affecting rsync options such as remote shell/path options and abbreviation variants. | Reject execution/destructive control options and abbreviations; insert `--` before source/target. |
| SA-05 | High | secure store | Store/library paths, key/salt/database files, ACL labels and creation modes had incomplete traversal/symlink/permission guarantees. | Validate simple library names, reject symlink paths, enforce ownership/modes, create private files safely, descriptor-validate private reads, and validate ACL/caller/name fields. |
| SA-06 | High | content store | Collision-prone hashes and path-based file checks weakened adversarial content identity. | CAS rejects MD5/SHA-1, validates roots/fanout paths, and opens source files with no-follow/fstat semantics. |
| SA-07 | Medium | persisted input | Benchmark result JSON used unbounded reads and worker/Git helpers had unbounded captured output. | Bounded byte reads plus structural validation; worker and Git helpers use bounded subprocess capture/timeouts. |
| SA-08 | Medium | URI authority | Host validation did not explicitly reject backslashes/control characters. | Reject control/backslash authority characters before URI construction. |
| SA-09 | Medium | redaction | Secret-key values with non-string scalar types could pass through unmasked. | Secret-context scalar values are masked consistently. |
| SA-10 | Medium | diagnostics | Validator, logging, experiment and generic diagnostic paths could expose arbitrary exception/input text. | Type/structure-only public diagnostics, full context redaction, sanitized log metadata and `diagnose=False`. |
| SA-11 | Medium | resource controls | NaN/infinity/boolean edge cases could bypass positive-number/count assumptions or produce pathological retry calculations. | Added finite/type validation and saturating retry-delay behavior across limits, cache, retry, resilience, rate limiting and upstream policy. |
| SA-12 | Medium | CI supply chain | GitHub Actions used moving version tags. | Pin checkout/setup-python to immutable commit SHAs. |
| SA-13 | High | crypto | Legacy predictable hostname/user passphrase helper remained callable and decrypt accepted plaintext as a silent downgrade. | System-derived passphrase helper now fails closed; plaintext decryption is rejected unless explicit migration opt-in is supplied; salt/format validation tightened. |
| SA-14 | Medium | diagnostics | Benchmark worker failures embedded raw child stderr in raised errors. | Public error now contains only exit status; raw stderr remains available only in the explicit result object. |
| SA-15 | Medium | diagnostics | GitPython and stdlib argument-binding wrappers copied arbitrary exception text into public errors. | Normalize to exception type/stable structural messages; add secret-bearing regression tests. |
| SA-16 | Medium | benchmark artifacts | Artifact registration/run packaging could follow or race symlinked/replaced sources. | Descriptor/path identity validation, exclusive output creation, no-follow source opens, output directory checks, and atomic run metadata publication. |
| SA-17 | Medium | directory hashing | Directory enumeration could be followed by a later path-based open after a symlink swap. | Hash listed files through `open_path_under_base` so validation is bound to the opened path components. |
| SA-18 | Medium | numeric/DoS | Several resource and timing APIs accepted non-finite controls. | Package-wide numeric security regression tests enforce finite values and proper integer/count types. |
| SA-19 | Medium | CI tooling | The repository pinned pytest 9.0.2, which is affected by CVE-2025-71176 local tmpdir handling. | Raise all maintained pytest pins to 9.0.3 and enforce the patched pin in repository contract tests. |

## Dependency and advisory review

The audit distinguishes dependency advisories from local source findings.

- **Pydantic**: CVE-2024-3772 / GHSA-mr82-8j83-vxmv affects
  `>=2.0.0,<2.4.0`; the branch floor is `>=2.4.0`.
- **GitPython**: multiple 2026 reviewed advisories affect `<=3.1.58` and are
  patched in `>=3.1.59`; the branch floor is `>=3.1.62`.
- **Cryptography**: 2026 security fixes landed in the 46.x line; the branch
  requires `>=50.0.1`, above those patched versions.
- **Matplotlib**: the `axes.prop_cycle` expression-evaluation hardening was
  backported to 3.10.9; the branch floor is `>=3.10.9`.
- **Loguru**: the existing `>=0.7.0` floor is already above the historical
  security-fixed 0.5.3 release.
- **pytest**: CVE-2025-71176 affects versions `<9.0.3`; maintained CI/local
  setup pins are raised to `9.0.3`.

An advisory search is time-bounded evidence, not proof that a dependency has no
unknown vulnerability.

## Permanent security regression contracts

The audit adds or extends tests for:

- package-wide source parsing;
- banned executable/deserialization primitives;
- no production `assert`;
- no explicit TLS-verification disablement;
- dependency security floors;
- bounded subprocess output;
- path-component symlink rejection;
- rsync control-option rejection;
- secure-store ownership/mode/symlink/ACL behavior;
- CAS collision-resistant identity and symlink behavior;
- benchmark JSON/output bounds;
- numeric finite resource controls;
- secret-safe validation/logging/diagnostics;
- cryptographic downgrade rejection.

## Residual trust boundaries

These are design boundaries, not findings silently left unfixed.

### Installed plugins execute code

`discover_plugins()` imports Python entry points and may instantiate them.
Installed plugin packages therefore execute with the current process privileges.
Consumers that accept untrusted plugin selection need their own allowlist,
process isolation, or sandbox.

### TCP reachability can become SSRF

`tcp_reachable()` intentionally connects to a caller-selected host/port. If a
remote user controls those values, the consuming application must apply network
allow/deny policy.

### Provenance allowlists can still include secrets

Environment capture is explicit and allowlisted, but an application can still
choose a secret-bearing variable. Do not allowlist tokens/passwords.

### SecureStore ACLs are cooperative labels

ACL caller strings are application-supplied identifiers, not authentication of
malicious code already executing in the same process. File-key mode also relies
on OS account/file permissions; an attacker that can read the entire private
configuration directory can read the adjacent key.

### Platform path guarantees differ

Descriptor-relative `O_NOFOLLOW` hardening is strongest on POSIX. Fallback
platforms rely on containment validation plus ordinary open and cannot fully
eliminate the same class of TOCTOU race.

### Generic parsers are intentionally generic

`json_loads`, `iter_jsonl`, generic serialization and several data
structures do not impose universal input-size/nesting budgets. APIs advertised
for untrusted persisted input use explicit bounds; downstream applications
must bound other attacker-controlled streams according to context.

### Benchmark/profiling APIs execute programs by design

Benchmark worker, process profiling, perf integration and rsync are local
execution primitives, not sandboxes. Do not expose executable/module/argument
selection directly to untrusted remote users.

### Weak hashes remain compatibility options

Generic hashing continues to expose MD5/SHA-1 for legacy/non-adversarial
fingerprints. Security-sensitive content identity rejects them.

## Full source inventory

The audited package contained 97 Python files:

### Package root

`__init__.py`, `_version.py`, `async_utils.py`, `binary.py`,
`buffers.py`, `cache.py`, `collections.py`, `concurrency.py`,
`config.py`, `content_store.py`, `context.py`, `dag.py`,
`deprecation.py`, `diagnostics.py`, `dict_utils.py`, `enums.py`,
`env.py`, `experiments.py`, `faults.py`, `formatting.py`, `fs.py`,
`hashing.py`, `identifiers.py`, `instrumentation.py`, `io.py`,
`iteration.py`, `leases.py`, `limits.py`, `models.py`, `network.py`,
`parsing.py`, `partitions.py`, `pipeline.py`, `plugins.py`,
`project.py`, `provenance.py`, `provenance_graph.py`, `rate_limit.py`,
`redaction.py`, `resilience.py`, `resources.py`, `result.py`,
`retry.py`, `sampling.py`, `security.py`, `serialization.py`,
`signals.py`, `stats.py`, `streaming.py`, `structures.py`,
`subprocess.py`, `sync.py`, `testing.py`, `testkit.py`,
`time_utils.py`, `timing.py`, `typed_config.py`,
`upstream_protocol.py`, and `versioning.py`.

### Optional backends

`ext/__init__.py`, `ext/observability_loguru.py`,
`ext/project_gitpython.py`, `ext/project_stdlib.py`,
`ext/secure_crypto.py`, `ext/secure_store.py`,
`ext/validation_pydantic.py`, and `ext/validation_stdlib.py`.

### Benchmark package

`benchmark/__init__.py`, `artifacts.py`, `backends.py`, `build.py`,
`cli.py`, `compare.py`, `diagnostics.py`, `environment.py`,
`experiment.py`, `export.py`, `gate.py`, `history.py`, `io.py`,
`metrics.py`, `overhead.py`, `perf.py`, `performance.py`, `plot.py`,
`policy.py`, `process.py`, `protocol.py`, `report.py`, `result.py`,
`run_directory.py`, `runner.py`, `safe_io.py`, `schema.py`, `suite.py`,
`trends.py`, and `worker.py`.

## Verification status

Feature-branch pushes intentionally do not run hosted CI.

Before this audit branch is merged, the expected local/full gates are:

```bash
python scripts/release.py check
python -m ruff check src tests benchmarks scripts
python -m mypy src/gunz_utils
python -m pytest
python scripts/ci.py docs
python scripts/ci.py packaging
```

After merge (or a PR targeting `main`), hosted `CI / verify` must additionally
complete the Python 3.12 suite.

Do not mark this audit closed merely because the source review is complete; the
branch remains pending full executable verification until those gates pass.
