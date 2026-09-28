# Security Audit Methodology

This document defines the repeatable deep-security review process for
`gunz-utils`. It complements `SECURITY.md` (reporting/disclosure) and
`AGENTS.md` (day-to-day security rules).

## Scope

A deep audit covers:

- every Python source file under `src/gunz_utils/`;
- dependency floors and optional extras in `pyproject.toml`;
- package/build isolation and PEP 561 packaging;
- GitHub Actions and other executable repository automation;
- public APIs that cross filesystem, process, network, serialization,
  cryptographic, plugin, logging, or concurrency trust boundaries.

Historical task records are evidence, not current policy.

## Phase 1: complete source inventory

Enumerate the package tree from the audited commit and record the number and
paths of all `*.py` files. The audit is incomplete until every source file has
been mechanically inspected.

## Phase 2: package-wide mechanical scan

Inspect every source file for at least:

- dynamic code execution: `eval`, `exec`;
- shell execution: `shell=True`, `os.system`, `os.popen`;
- unsafe deserialization: pickle, marshal, shelve, unsafe YAML loaders;
- subprocess creation, captured output, timeout and cancellation behavior;
- temporary-file creation and publication;
- path containment, symlink/hard-link handling, and check-then-use races;
- filesystem permissions and atomic replacement;
- network authority/URI construction and TLS verification controls;
- cryptographic primitives, key derivation, nonce/salt handling, and weak hashes;
- environment capture and diagnostic/logging output;
- dynamic imports and plugin entry-point execution;
- unbounded input parsing, output capture, queues, retries, and numeric budgets;
- broad exception handling and raw exception-message propagation;
- production `assert` statements.

The repository regression suite should encode mechanically enforceable rules.

## Phase 3: trust-boundary manual review

Mechanically suspicious APIs are not automatically bugs. Review their complete
control and data flow.

### Filesystem

Check traversal, absolute paths, null bytes, intermediate and final symlinks,
hard-link semantics, TOCTOU windows, ownership/mode, temporary-file creation,
atomic publication, replacement behavior, and behavior in attacker-writable
parent directories.

When validation and use are security-sensitive, prefer descriptor-relative
operations and validate the opened object with `fstat`.

### Processes

Require argv-style execution without an implicit shell. Review executable/path
selection, environment inheritance, timeout behavior, process cleanup,
cancellation, bounded stdout/stderr, and whether helper options can alter
execution (for example rsync remote-shell options).

### Cryptography and secrets

Require explicit secret key material, authenticated encryption, safe
salt/nonce lengths, maintained dependency versions, restrictive key-file
permissions, fail-closed downgrade behavior, and diagnostics that do not copy
secret values.

Weak hashes may remain for compatibility only when their non-security role is
clear; they must not be accepted for adversarial content identity.

### Network

Validate URI delimiters, control characters, IPv6/IDNA behavior, port/time
bounds, and SSRF implications. Generic connectivity helpers are not network
sandboxes; callers must enforce destination policy when input is untrusted.

### Parsing and serialization

Prefer non-executable formats. Bound input size where an API claims to handle
untrusted persisted input. Review nesting, cycles, count/length limits, and
NaN/infinity behavior for resource controls.

### Concurrency

Review cancellation, queue/concurrency bounds, stale lease ownership, lock-file
races, failure cleanup, and whether success can be published after ownership is
lost.

### Diagnostics and plugins

Exception text, child stderr, validator messages, URLs, and environment values
can contain secrets. Public diagnostics should expose stable type/structure
metadata by default.

Entry-point loading executes installed code by design. Treat plugin packages as
trusted unless a consumer adds an allowlist/sandbox boundary.

## Phase 4: dependency/advisory review

For every optional dependency floor:

1. search current upstream/GitHub reviewed advisories;
2. identify affected and patched versions;
3. raise the floor when the repository currently permits an affected release;
4. add a repository contract test for security-significant floors;
5. document why the floor exists.

Do not claim that absence of a search result proves a dependency has no
vulnerabilities.

## Phase 5: adversarial review of the fixes

After remediation, re-scan every modified source file. Specifically look for:

- a check that still occurs before an unbounded read/open;
- a symlink check followed by a later path-based open;
- a size/output limit applied only after allocation;
- exception text reintroduced through a wrapper;
- migration compatibility that silently downgrades security;
- a blocklist bypass through option abbreviation or alternate syntax.

## Phase 6: verification

Before merge, run the canonical repository gates when the environment permits:

```bash
python scripts/release.py check
python -m ruff check src tests benchmarks scripts
python -m mypy src/gunz_utils
python -m pytest
python scripts/ci.py docs
python scripts/ci.py packaging
```

The full gate is:

```bash
./scripts/verify.sh
```

Hosted CI additionally repeats the full test suite on Python 3.12 after the
branch is merged or proposed to `main`.

## Severity language

The audit uses repository-local risk tiers (critical/high/medium/low) to
prioritize remediation. These are not CVSS scores and do not assign CVE IDs.

A source defect in `gunz-utils` is not a CVE unless a CNA assigns one.
Dependency CVEs/GHSAs should be cited separately from local findings.

## Audit limitations

This process is source and dependency review, not a claim of formal security
certification. It does not replace:

- external penetration testing;
- fuzzing at every input boundary;
- operating-system or container hardening;
- malicious dependency/runtime compromise analysis beyond reviewed advisories;
- application-specific authorization and network policy in downstream users.
