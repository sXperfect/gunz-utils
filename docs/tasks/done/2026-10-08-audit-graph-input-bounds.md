# AU-05: Graph depth and bounded external input

**Date:** 2026-10-08
**Role:** Audit researcher
**Status:** Done — initial review; scoped repair results recorded below
**Priority:** P2
**Parent:** [Audit follow-up](2026-10-08-audit-follow-up.md)
**Baseline:** `80bde76a641ce4577574fde60ec957251aee2ba0` plus existing dirty tree

## Question and scope

Do the current implementations uphold their documented security, correctness,
boundedness, and failure contracts? Scope: dag.py and provenance_graph.py traversal; serialization.py, streaming.py, redaction.py, iteration.py, limits.py, network.py, subprocess.py, sync.py, provenance.py, env.py at input boundaries.

## Review obligations

Recursive graph depth (GAP-002), deterministic ordering and cycle rollback, byte/item/depth bounds before allocation, finiteness/bool/count domains, timeout/cancellation, argv/URI validation, and secret-safe diagnostics. Separate generic caller-budgeted APIs from APIs promising bounded untrusted input.

## Method and verification

Use deep chain/cycle graphs plus an independent iterative oracle. Inspect existing bounded capture, streaming, numeric, redaction, and security tests; probe only uncovered contracts with synthetic inputs and bounded resources. Link AU-03 for lifecycle overlap.

Read and obey the parent's shared execution contract. During the initial review,
this file is the worker's only permitted tracked write. Implementation repairs
are proposed for a separately coordinated follow-up.

Existing audit environment candidate:
`/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python`.
The coordinator confirmed Python 3.11, pytest, mypy, and cryptography are
available; Ruff is absent. Record actual tool versions and results yourself.

## Deliverables and acceptance

- [x] Source and relevant test inventory reviewed.
- [x] Contract/trust model and parameter domains recorded.
- [x] Findings separated into confirmed defects, proof gaps, stale records,
      and accepted limitations, with source locations and severity rationale.
- [x] Executed commands, results, skips, and reproducible trigger recorded.
- [x] Follow-up repairs specify file ownership, dependencies, and regression checks.
- [x] Coordinator receives a concise findings summary.

## Findings

### Inventory, trust model and domains

Read all scoped sources: DAG traversal (also reviewed in AU-03),
`provenance_graph.py`, `serialization.py`, `streaming.py`, `redaction.py`,
`iteration.py`, `limits.py`, `network.py`, `subprocess.py`, `sync.py`,
`provenance.py`, and `env.py`. Inspected relevant tests listed in verification,
registry GAP-002, plus AU-02's salt/payload proof gaps and the matching secure
source sections. No implementation changes made.

Callbacks, stream implementations and iterable inputs are caller-controlled;
network host strings and subprocess output may be untrusted. Core helpers do not
sandbox callbacks/child processes. Generic JSON loaders/materializers and
redaction traversal have no universal input-byte/item budget. Limits and
ResourceBudget are opt-in cooperative checks, not automatic parser enforcement.

Reviewed domains: positive integer chunk sizes, batch/group sizes and flatten
max_nesting; nonnegative depth/count/byte limits, all rejecting bool; ResourceBudget
finite nonnegative timeout and finite injected clock; URI schemes and port
1..65535, DNS IDNA/IPv6 normalization, authority delimiter exclusion; TCP timeout
finite positive; subprocess timeout finite nonnegative and max_output_bytes
nonnegative integer or None. Sync's missing finiteness validation is F3 below.

Invariants: explicit writer budgets never retain/write more than configured
limit; digest covers committed bytes only; invalid input should precede I/O;
graph cycle rejection rolls back replacements; deterministic traversal preserves
declared input order; URI host normalization must not manufacture authority/path
separators; captured output has a shared stdout/stderr retention cap and capture
completion must respect configured timeout.

### AU-05-F1 — IDNA normalization bypasses authority validation (medium, confirmed)

Source: `src/gunz_utils/network.py:68-74`, `:99-103`, `:124`.
Raw host delimiter checks happen **before** IDNA encoding, with no validation of
the resulting ASCII DNS host. Trigger: host `example\uff20evil.test` (U+FF20
fullwidth commercial at). Observed:

```text
URI: https://example@evil.test
urllib.parse.urlsplit(uri).hostname: evil.test
```

Fullwidth slash U+FF0F produces `https://example/evil.test`, turning a host suffix
into a path; fullwidth colon U+FF1A produces `https://example:123`, supplying an
unrequested port. These are synthetic strings only; no requests were issued.

Contract: API accepts host separately and promises ordinary URI authority
semantics; `test_build_network_uri_idna_normalizes_dns_host` preserves Unicode
DNS support, while `test_build_network_uri_rejects_authority_injection_and_bad_brackets`
rejects the direct ASCII @ case. Unicode normalization must preserve those
separate component boundaries. Medium local security risk because callers using
untrusted host strings can generate requests to an unintended parsed destination;
this helper alone is not an application host allowlist or SSRF sandbox.

Repair: validate the encoded ASCII DNS host with the same delimiter/control
constraints plus colon/bracket rejection for the DNS branch before composing
userinfo/port/path. Preserve valid IDNA DNS names, IPv4 and explicit IPv6 handling.
Regression: ASCII and fullwidth authority/path/port separators, valid Unicode
DNS, encoded userinfo and parsed-host equivalence.

### AU-05-F2 — bounded synchronous capture timeout excludes pipe draining (medium, confirmed)

Source: `src/gunz_utils/subprocess.py:189-201`, routed by
`run_command` when `max_output_bytes` is supplied. `process.wait(timeout=...)`
only bounds the direct child's exit; subsequent reader-thread joins have no
remaining deadline.

Trigger: direct Python child launches a descendant inheriting stdout/stderr,
then exits promptly; descendant sleeps 0.25s without producing output. Call
`run_command(..., timeout=0.05, max_output_bytes=32)`. Observed success after
**0.279s**, rather than timeout. The synthetic descendant exits naturally;
no long-running process was left behind. A permanently retained pipe implies
unbounded join by inspection, not an executed forever-hanging probe.

Contract: public API exposes subprocess timeout and captured result together;
`rsync_mirror` documents timeout as the subprocess timeout. Bounded retention
must not remove timeout enforcement for capture completion. Existing
`test_bounded_output_kills_descendant_pipe_holders` exercises output overflow
while the direct process remains alive, not successful direct exit with a quiet
pipe holder. Medium availability/resource risk when captured child process trees
are untrusted. The affected mode is specifically synchronous bounded capture;
no claim of identical behavior in async/unbounded paths is made from this probe.

Repair: maintain an operation deadline through process wait and reader joins;
kill the owned process group and drain/close resources on expiry while preserving
TimeoutExpired semantics. Add controlled silent descendant coverage after parent
exit; verify stdout/stderr budget conservation, overflow precedence and timeout
cleanup. Escaped process-group descendants/platform behavior require an explicit
supported cleanup contract rather than an unlimited join.

### AU-05-F3 — invalid sync timeout mutates completion marker before rejection (low, confirmed)

Source: `src/gunz_utils/sync.py:204-210`, `:251-253`, `:286-288`.
NaN/+inf pass local timeout validation; downstream `run_command` rejects them,
after directory/lock setup and existing marker deletion.

Trigger: synthetic destination containing `.gunz-sync-complete`; pass timeout=NaN,
lock=False. Patch only shutil.which to simulate available rsync; real run_command
validation rejects before any process spawn. Observed ValueError and **existing
completion marker removed**. No sync command was run. Low because invalid caller
input destroys coordination evidence rather than transferring/deleting payloads.
Existing subprocess finite-domain tests pass, but sync tests do not assert
validation-before-marker-mutation for nonfinite timeout.

Repair: finite timeout validation at sync entry before filesystem effects;
consider normalized source validation before mkdir as part of the same validation
ordering change. Regression: NaN/+inf/-inf/bool/time domain values leave directory,
lock and marker state unchanged and do not call subprocess execution.

### GAP-002 reproduced — deep graph recursion (documented limitation)

At ordinary interpreter recursion limit, synthetic 1100-node chain:

- WorkflowDAG construction with reverse-listed dependencies: RecursionError.
- Parent-first construction succeeds, but last effective_fingerprint recurses
  into RecursionError.
- Parent-first ProvenanceGraph construction succeeds; ancestors(last) raises
  RecursionError.
- Replacing first provenance node to form a deep cycle raises RecursionError
  before cycle-specific ValueError, but restores the previous node correctly.

Sources: `dag.py:_topological_order/effective_fingerprint` and
`provenance_graph.py:ancestors/_validate_acyclic`. Independent iterative chain
oracle confirms all 1100 dependencies precede their consumers. This is already
explicit in registry ALG-009/011 and GAP-002, so retain it as an accepted current
limitation requiring a design/repair decision, not a newly discovered vulnerability.

Propose iterative DFS with explicit enter/exit stack to retain current stable
order and unresolved-parent semantics; reuse fingerprint memoization across
execution to avoid repeated traversal. Graph construction currently validates the
whole provenance graph per add, giving quadratic cumulative work on growing
chains; batching/budgets need an explicit API decision.

### Further proof/resource gaps and coordination

- JSON serialization's default depth=100 and flatten's default max_nesting=256
  provide recursion guards; raising configured limits above Python recursion
  capacity can still cause RecursionError. JSON loading is a documented stdlib
  wrapper with no size/depth bound. JSONL is lazy by record, not by line byte size;
  writes buffer up to 256 serialized records with caller-controlled record size.
  Keep those documented caller-budgeted limitations distinct from bounded writers.
- BoundedWriter/DigestWriter enforce output before writes and maintain committed
  byte counters across partial writes. copy_and_hash caps output, but may read one
  full chunk beyond remaining output budget; max_bytes is not an allocation cap.
  Streams must honor read/write contracts. No new writer defect confirmed.
- redact_dict traversal has no cycle/depth budget and only partially validates
  show_chars at entry; caller-bound shape/domain proof is needed. Its docstring
  examples/same-length claim diverge from current redact behavior; classify as
  documentation repair, not secret exposure from the tested masking logic.
- TCP connect timeout is per resolved address and does not bound DNS lookup or
  the total address loop. This is a contract clarification/proof gap; no actual
  network was contacted by probes. Allow-private=False validates addresses before
  connecting numerically; current tests exercise this protection.
- Provenance environment capture requires explicit allowlist; secret names and
  ordinary URI password userinfo are redacted. Arbitrary config values/custom
  cast exception causes can retain secrets; callers own configuration selection
  and diagnostic traceback policy. No new exposure confirmed in this pass.
- AU-02 salt/payload gap confirmed by inspection: secure_store._read_private at
  line 466 calls unbounded read; salt length is not validated before _derive_key
  at 742; secure_crypto decodes every hex component before exact fixed-component
  length checks at 104-113. Bound fixed key/salt reads before allocation/KDF and
  validate encoded fixed-size lengths before unhexlify. Ciphertext/value maximum
  size requires a documented policy decision, not an invented universal limit.
  Leave secure source repair ownership with AU-02 to avoid overlapping edits.
- AU-03 owns pipeline/cancellation findings; none duplicated here. No new
  A3/A4 level or full-audit certification is claimed.

## Verification evidence

Baseline HEAD: `80bde76a641ce4577574fde60ec957251aee2ba0` plus preexisting dirty
CHANGELOG/release fragments/pyproject/enums/models and coordinator task files.
Scoped implementations/tests were not modified. Sole tracked write is this file.
Python `/home/adhisant/tmp/miniforge3/envs/gunz-utils/bin/python`: **3.11.14**;
pytest **9.0.2** (version confirmed during AU-03).

Executed from repository root with that interpreter:

```bash
python -m pytest -q tests/test_core/test_serialization.py tests/test_core/test_redaction.py tests/test_core/test_iteration.py tests/test_core/test_provenance_graph.py tests/test_core/test_provenance.py tests/test_core/test_network.py tests/test_core/test_subprocess.py tests/test_core/test_sync.py tests/test_core/test_security_numeric_contracts.py tests/test_core/test_security_audit_regressions.py tests/test_core/test_shared_foundation.py tests/test_core/test_foundation_more.py
# 195 passed, 96 subtests passed, 1 warning in 8.09s; no skips
python -m pytest -q tests/test_core/test_a0_foundation_algorithms.py tests/test_core/test_algorithm_audit_contracts.py tests/test_core/test_foundation_io_retry.py
# 61 passed, 1 warning in 4.64s; no skips
PYTHONPATH=src python tmp/au05/probe.py
# Exit 0; observed normalization, graph, timeout and marker results above
```

Total **256 tests, 96 subtests passed**. Both warnings concern the deprecated
benchmark namespace import. Probe prints failures as observed outcomes rather
than certifying invariants; source stays read-only. Synthetic graph 1100 nodes,
child runtime 0.25s and disposable marker bound probe resources. Ignored script
is local evidence, not a regression test checked into repository.

Initial sandbox initialization failure established during AU-03; narrowly scoped
escalated local read/test/probe executions succeeded. No installs or external
reporting. Canonical full gate and external advisories were outside this review.

## Proposed follow-up tasks

1. **AU-05-R1, P1: URI normalization validation**. Own network.py,
   tests/test_core/test_network.py and a coordinated security fragment. Independent
   of graph/process work; regressions described in F1. Existing Unicode DNS and
   IPv6 behavior must remain supported.
2. **AU-05-R2, P1: captured-pipe deadline/cleanup**. Own subprocess.py and
   tests/test_core/test_subprocess.py. Coordinate with AU-03 lifecycle repairs if
   expanding repeated-cancellation/task-setup cleanup; initial synchronous fix
   can be separate. F2 silent descendant, timeout, overflow and capture tests.
3. **AU-05-R3, P2: sync validation ordering**. Own sync.py and
   tests/test_core/test_sync.py. Coordinate filesystem lock/publication source
   concerns with AU-01; finiteness entry validation is independently scoped.
4. **AU-05-R4, P2: iterative graph traversal/explicit bounds**. Own dag.py and
   provenance_graph.py plus graph proof tests. Coordinate DAG ownership with
   AU-03's proposed proof expansion. Cover deep chains/cycles, stable order,
   unresolved ancestors, replacement rollback and independent small-graph oracle.
   No arbitrary graph-size default should be introduced without contract review.
5. **AU-02-R4 dependency: fixed-size crypto material validation**. AU-02 remains
   sole owner of secure source/tests. Validate 16-byte salt and 44-byte Fernet
   material via bounded descriptor read; AES fixed encoded lengths before decode;
   decide/configure variable payload budgets separately.
6. **AU-06: evidence reconciliation and integration**. Record confirmed current
   gaps, preserve existing graph limitation notes, and reconcile levels only after
   applicable repairs/focused checks and canonical gate succeed.

Review complete; confirmed defects remain unrepaired. Coordinator owns creation
and scheduling of repair task files and shared registry/index changes.

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
