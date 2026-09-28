# Security Audits & Vulnerability Assessments

This directory contains security audit documentation, vulnerability assessment reports, and audit roadmaps for `gunz_utils`.

## Document Index

- [Vulnerability Assessment Report — Round 1 (2026)](vulnerability-assessment-2026.md)
  - `VULN-2026-001`: Option / Argument Injection via Unsanitized Leading Dash Characters in `sanitize_filename`
  - `VULN-2026-002`: Insecure Parent Directory Permissions & Creation Window in `atomic_write`
  - `VULN-2026-003`: ReDoS & CPU Resource Exhaustion Potential in Input Sanitization Routines
- [Vulnerability Assessment Report — Round 2 (2026)](vulnerability-assessment-round2-2026.md)
  - `VULN-2026-004`: Option / Flag Injection Potential via Remote Source Strings in `rsync_mirror`
  - `VULN-2026-005`: Sensitive Environment Variable Leakage via Broad Key Matching in Provenance Capture
  - `VULN-2026-006`: Local SQLite Database Lock Starvation / Denial of Service in `SecureStore`
- [Vulnerability Assessment Report — Round 3 (2026)](vulnerability-assessment-round3-2026.md)
  - `VULN-2026-007`: SSRF & Uncontrolled Target Connection Vulnerability in `tcp_reachable`
  - `VULN-2026-008`: Memory Exhaustion & Unbounded Recursion in `to_jsonable`
  - `VULN-2026-009`: Subprocess Execution Flag Hijacking via Custom Python Interpreter Path in `run_python_worker`
- [Vulnerability Assessment Report — Round 4 (2026)](vulnerability-assessment-round4-2026.md)
  - `VULN-2026-010`: Time-of-Check to Time-of-Use (TOCTOU) Symlink Race Window in `transactional_directory`
  - `VULN-2026-011`: Directory Symlink Traversal Crash & Denial of Service in `directory_manifest`
  - `VULN-2026-012`: CPU Resource Exhaustion / DoS via High PBKDF2 Iteration Counts in `get_derived_key`

---

## Audit Coverage & Component Roadmap

### Audited Components (Phase 1 through Phase 4 Focus)
- `src/gunz_utils/security.py` — Input sanitization, path joining, path-containment opening.
- `src/gunz_utils/io.py` — Atomic file writing, directory creation, permissions.
- `src/gunz_utils/subprocess.py` — Command execution, bounded output capture, process group termination.
- `src/gunz_utils/provenance.py` — Runtime provenance capture, environment variable allowlists, execution manifests.
- `src/gunz_utils/sync.py` — Rsync mirror abstraction, argument validation, advisory locking.
- `src/gunz_utils/content_store.py` — Content-addressed store, hash integrity, fanout symlink checks.
- `src/gunz_utils/ext/secure_store.py` — Fernet encrypted store, SQLite audit log, file key & passphrase modes.
- `src/gunz_utils/redaction.py` — Secret value masking, dict/list recursive walking.
- `src/gunz_utils/network.py` — URI authority construction, TCP socket connection safety.
- `src/gunz_utils/serialization.py` — Deterministic JSON serialization, type conversions, depth limits.
- `src/gunz_utils/benchmark/worker.py` — Isolated python worker execution and strict JSON parsing.
- `src/gunz_utils/fs.py` — Transactional directory creation and atomic directory replacement.
- `src/gunz_utils/hashing.py` — File and directory manifests, streaming file digests, short hashes.
- `src/gunz_utils/ext/secure_crypto.py` — AES-256-GCM authenticated encryption and PBKDF2 key derivation.

### Prioritized Audit Focus Areas (Upcoming / Continuous)
1. **Provenance & Environment Variable Capture (`provenance.py`, `env.py`)**: Ensure environment allowlists do not accidentally expose auth tokens or system credentials.
2. **External Process & Sync Boundary (`sync.py`, `subprocess.py`)**: Ensure rsync parameters, remote URLs, and subshell invocation controls block arbitrary flag injection.
3. **Storage & Content Integrity (`content_store.py`, `fs.py`)**: Verify symlink traversal prevention across fanout directories and multi-process file replacement locks.
4. **Credential Isolation & Cryptography (`ext/secure_store.py`, `ext/secure_crypto.py`)**: Verify key derivation iteration counts, SQLite permission windows, and Fernet token validation safety.
5. **Rate Limiting & Network Primitives (`rate_limit.py`, `network.py`)**: Evaluate socket timeouts, URI authority parsing, and denial-of-service via memory inflation in sliding window rate limiters.
