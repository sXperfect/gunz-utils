# AU-01: Filesystem publication

**Date:** 2026-10-08
**Role:** Audit researcher
**Status:** Done — initial review; scoped repair results recorded below
**Priority:** P1
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Baseline:** `80bde76a641ce4577574fde60ec957251aee2ba0` plus existing dirty tree

## Scope, contract, and trust model

Reviewed filesystem-boundary implementation and tests for `content_store.py`,
`fs.py`, `io.py`, the path-opening section of `security.py`, file hashing and
manifest traversal in `hashing.py`, and publication interaction in
`benchmark/run_directory.py`. This is a focused first review, not a complete
security certification or A3/A4 promotion. Read repository `AGENTS.md`,
`SECURITY.md`, the security audit methodology, and algorithm correctness guide.

- CAS: collision-resistant algorithms only; positive non-boolean integer chunk
  sizes; non-negative integer fanout depth; positive integer fanout width with
  total consumed characters bounded by digest length. Accepted digest input is
  documented as fixed-length hexadecimal. Existing artifacts must match digest
  and optional size; publication promises safety for cooperating same-digest
  writers. Streaming memory is O(chunk_size), work O(content bytes).
- Atomic write: str/Path target, text/binary content matching mode, explicit
  integer permission range 0..0o7777 excluding bool. Private temporary content,
  atomic replacement, optional fsync. Post-replace fsync failure can raise with
  new bytes already visible, as expressly documented.
- Transactional directory: staging is owner-private via mkdtemp; success
  publishes staging atomically; implementation intends to reject existing
  destinations. No crash durability promise is stated.
- Path opener: read-only regular files, containment checks, POSIX component
  traversal using directory descriptors and O_NOFOLLOW. The configured root
  itself and its ancestor directories remain a trust anchor; other platforms
  use a path-based fallback.
- Adversarial publication probes below assume an actor can mutate the store's
  fanout or the destination parent. These are conditional filesystem-boundary
  failures, not a claim that an actor without those permissions can exploit
  them. Temporary-name guessing is practical for an actor able to list/watch
  the writable destination directory. Cooperating-writer fallback replacement
  is evaluated separately and does not show corrupted bytes.

## Confirmed findings

### AU01-F1 — Fanout symlink substitution redirects CAS publication (high, conditional)

**Location:** `content_store.py:164-195, 221-226`.
After `_ensure_prefix_directory` checks/creates the fanout path, publication
still calls path-based `os.link`. Deterministic interposition immediately before
linking removes the empty fanout directory and replaces it with a symlink to a
synthetic outside directory. `put_bytes` returns success; the artifact is
created outside the store root; subsequent `store.verify` returns false because
it now rejects the symlink. This defeats the fanout-rejection boundary when
store directory mutation is in the threat model. Existing static root/fanout
symlink tests pass but do not cover this interleaving. The same descriptor-based
review should cover verification and materialization source identity.

### AU01-F2 — Materialization releases its reserved staging name (high, conditional)

**Location:** `content_store.py:417-438`.
`mkstemp` is closed and unlinked before `shutil.copy2` opens that name again.
A writable-parent adversary can insert a symlink between those operations.
The probe inserts a symlink immediately before the real copy call: a synthetic
outside victim is overwritten with artifact bytes, and final publication returns
an output that is itself a symlink. Default `strategy="copy"`, `replace=False`,
and normal verification are sufficient. Existing materialization tests check
copy isolation and existing-destination behavior; they do not check temporary
name substitution. Keep the temporary descriptor/inode reserved while copying;
validate/anchor source and destination operations instead of reopening names.

### AU01-F3 — Transactional directory can replace a concurrent empty target (medium)

**Location:** `fs.py:59-63`.
Create a competing empty destination immediately after existence checks but
before real `os.replace`: replacement succeeds and the destination inode changes
to the staged inode. The intended existing-target rejection is not atomic.
A competing non-empty directory normally fails replacement; the reproduced
case is specifically empty-directory replacement, not arbitrary symlink
following. Existing target-symlink and failed-replace cleanup tests pass.
Use an atomic no-replace mechanism or document and enforce a narrower
cooperating-publisher protocol with appropriate platform behavior.

### AU01-F4 — Atomic-write setup failure leaks its raw descriptor (medium)

**Location:** `io.py:75-85, 105-110`.
If `os.fchmod` raises before `fdopen` takes ownership, cleanup unlinks the
pathname but never closes the raw descriptor. The probe captures the actual
mkstemp fd and confirms `os.fstat(fd)` still succeeds with zero links after the
function raises. Repeated permission-setting failures can exhaust descriptors.
Normal permission and replacement-cleanup tests pass. Track descriptor ownership
and close it on all pre-fdopen failures, including fdopen construction failure.

### AU01-F5 — Digest validator accepts non-hexadecimal spelling (low)

**Location:** `content_store.py:105-121`.
`int(normalized, 16)` accepts syntax broader than hexadecimal digit strings.
Fixed-length examples containing leading whitespace, a minus sign, or an
underscore all pass `path_for`, contrary to its validation contract. This
changes canonical naming/input acceptance; no traversal or digest-collision
exploit was demonstrated. Use an explicit ASCII `[0-9a-f]` domain after
normalization; add signed/whitespace/underscore/non-ASCII rejection cases.

## Proof gaps, stale records, and accepted limitations

- **GAP-006 clarified:** force hard-link failure, then publish a cooperating
  same-digest file just before fallback `os.replace`. The winner inode is
  replaced, but final bytes match the digest. This demonstrates absent atomic
  no-replace semantics in fallback; it does **not** demonstrate broken
  same-content byte correctness. Cross-process fallback stress/fault proofs
  remain pending. Decide the required inode/immutability contract before
  prescribing serialization or a portable no-replace fallback.
- **GAP-005 is stale as an unspecified-semantics gap:** `io.atomic_write` now
  documents post-replace directory-fsync visibility, and
  `test_atomic_write_directory_fsync_failure_has_documented_visibility` passes.
  Reconcile the registry wording rather than infer rollback is promised.
- `get` returns a Path, not a pinned handle. Artifact verification followed by
  copying/linking is not descriptor-bound. Source substitution and regular
  hard-link mutation need further proof and a stated immutable/trusted-store
  ownership policy; static checks alone do not certify hostile writable stores.
- `directory_manifest` materializes/sorts all file paths (O(files) memory), skips
  containment ValueError but propagates some filesystem race errors. No bounded
  inventory or best-effort race tolerance promise is assumed.
- `atomic_write` parent creation with nested `parents=True` deserves a permissions
  probe: only the final requested directory mode is specified by pathlib.
  This is pending, not a confirmed disclosure defect; the file itself stays
  private under 0600 and staging mkstemp defaults.
- Explicit hardlink materialization allows mutation of the stored inode by
  design and requires read-only consumers, as documented. Default copy avoids
  that aliasing in ordinary trusted-parent use.
- Run-directory writing publishes artifacts incrementally and run.json last;
  no all-directory transaction is promised. Existing GAP-004 should remain
  an ownership/contract decision alongside the gunz-bench handoff.
- No Windows/no-O_NOFOLLOW behavior, real cross-process race, fsync-on-crash,
  stress test, full canonical gate, or complete source-security scan executed.

## Verification evidence

Interpreter: `/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python`,
Python 3.11.14; pytest 9.0.2. Linux/POSIX filesystem. Focused command:

```bash
/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python -m pytest -q \
  tests/test_core/test_content_store.py tests/test_core/test_io.py \
  tests/test_core/test_atomic_permissions.py tests/test_core/test_security.py \
  tests/test_core/test_security_audit_regressions.py tests/test_core/test_hashing.py \
  tests/test_core/test_hashing_structured.py tests/test_core/test_a1_algorithm_proofs.py
```

**Result:** 135 passed, 4 subtests passed, no skips, 1.23 seconds. Synthetic
probe command: `.../bin/python tmp/au01/probes.py`; exit 0. Temporary untracked
probe captures cooperating winner/final inode difference, outside fanout bytes,
transactional directory inode replacement, non-hex acceptance, victim overwrite
and output symlink during materialization, and open unlinked descriptor after
fchmod failure. The real implementation is called after deterministic
interposition; probes do not patch production source or persisted tests.

The first sandboxed command failed during bwrap loopback initialization before
execution. Narrow escalated local reads/probes/tests then succeeded. No install,
network request, branch switch, reset, commit, or external disclosure performed.
Current HEAD matches baseline. Existing dirty source files were `enums.py` and
`models.py`; metadata/changelog/task-index changes and removed release fragments
were already present. No source/test edits were made by this worker.

## Proposed follow-up tasks and ownership

1. **AU01-R1, P1, `content_store.py` plus filesystem regression tests:** combine
   F1/F2 and pinned verification/materialization review under one owner to avoid
   conflicting edits. Specify writable-root/parent threat model; use anchored
   descriptors and retained private staging. Add controlled fanout swap,
   temporary symlink insertion, source identity substitution, and copy/link
   failure cleanup regressions. Coordinate any shared secure path helper with
   AU-02 before editing `security.py` or SecureStore callers.
2. **AU01-R2, P1/P2, `fs.py` plus directory regression tests:** implement/test
   atomic no-replace semantics for competing empty-directory publishers,
   preserve staging cleanup and static symlink rejection. Depends on a platform
   contract decision; source ownership independent from R1.
3. **AU01-R3, P2, `io.py` plus atomic-write tests:** fix raw-fd ownership cleanup;
   inject fchmod and fdopen setup failures, check exact fd is closed, target
   bytes preserved, and staging removed. Preserve the documented post-replace
   fsync visibility behavior. Coordinate with AU-02's atomic-write call sites.
4. **AU01-R4, P3, `content_store.py` and digest tests:** strict digest character
   validation; same owner as R1 or sequence after it. Preserve uppercase
   normalization and all supported algorithm lengths.
5. **AU01-R5, P2 proof work:** real multiprocess fallback and failure injection,
   inode/byte preservation oracle, trusted-root boundary and nested-directory
   permissions proof. Registry GAP-005/006 reconciliation belongs to AU-06
   after results. Do not promote audit level without required repaired-tree
   gates and `./scripts/verify.sh`.

## Acceptance

- [x] Source and relevant test inventory reviewed within the stated scope.
- [x] Contract/trust model and parameter domains recorded.
- [x] Confirmed defects separated from proof gaps/stale records/limitations.
- [x] Commands, results, locations, and reproducible triggers recorded.
- [x] Repairs specify ownership, dependencies, and meaningful regressions.
- [x] Findings sent to coordinator.
- [ ] Repairs, broader proof work, and canonical repaired-tree verification.

## Final integration evidence — 2026-10-08

The scoped repair work passed the canonical aggregate verifier on
`audit/follow-up-20261008`, based on `80bde76a641ce4577574fde60ec957251aee2ba0`
plus the preserved user changes and this local repair tree. No commit, merge,
release, or publication was performed.

- Python 3.11.14 and 3.12.13: **1,244 passed, 22 intentional native-absent skips**
  per main suite; each interpreter also ran **57 compiled-native tests with zero
  skips**, and 35 fallback tests with 22 expected native skips. Counts overlap.
- Ruff 0.14.10 and mypy 1.19.1: pass across the complete configured scope
  (97 Python source files for mypy).
- Release metadata, strict Sphinx, all optional isolation cases, real plot,
  wheel/sdist separate installs, extracted-sdist wheel rebuild/install, and
  optional C activation: pass. Separate compiler-hidden sdist install: pass.
- Full aggregate result: all six gates return zero. Local evidence:
  `tmp/audit-20261008-final-summary.json` and
  `tmp/audit-20261008-final-verification.log`.
- Execution-input fingerprint: `b872b0f9f251f431f83f3e7433d2789e947be3a91f8144fa81d32690e882b222` (238 source/test/config,
  doc-source and package metadata files; excludes evolving audit records and
  generated files). Manifest: `tmp/audit-20261008-final-tree.json`.

Earlier pending/failed statements in the chronological review/repair evidence
refer to intermediate attempts. This final run followed the subprocess type
correction and the interpreter-independent native depth cutoff. Historical A4
levels are not blanket-promoted. The repository-wide algorithm proof program
remains active for the documented deeper graph, concurrency, crypto, platform,
resource-budget and cross-process proof obligations.
