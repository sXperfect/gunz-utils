# Remote audit: filesystem

Status: focused repairs complete; root integration gates pending
Parent: [Integration task](2026-10-11-remote-audit-repairs.md)
Checkout: /tmp/gunz-utils-fix-audit-20261011-672bfb1

## Ownership
Production: hashing.py and sync.py. Add dedicated tests without editing the shared existing
20261011 regression module. Update this task with evidence. Root owns shared docs.

## Scope
Fail-closed traversal including enumeration failures; symlink and race behavior; finite scratch-only rsync marker interruption and contention review.
Reproduce before repairing; inspect maintained contracts and existing tests.
Use narrow compatible changes. Explicitly document unresolved contract choices.
Run focused pytest and Ruff, report commands and results. Do not commit or publish.

## Reviewed inventory and reproduced failures

Read current AGENTS, parent execution boundaries, hashing and sync implementation
and existing hashing/structured/sync/timeout tests. Only this isolated checkout
was edited; main, SecureStore, shared regression file, registry and configuration
remained outside this agent's ownership.

1. `hashing.py:269` directory_manifest used pathlib.rglob, which suppresses
   directory enumeration OSError. Injecting PermissionError only at a restricted
   synthetic child scan (other scans real) silently omitted its regular file;
   root-level scan denial behaved similarly. Independent directory_manifest and
   directory_hash cases each should reject. Before repair: four strict failures,
   one positive symlink/hash case passed (Python 3.11, 0.27s).
2. Real **local rsync 3.2.7**, with tiny synthetic source/target files, copied a
   source `.gunz-sync.lock` over the target lock inode while the helper held the
   old inode's flock. Strict inode assertion failed: 6303573 became 6303574.
   This allows subsequent cooperating callers to lock a distinct inode; it is
   not a noncooperating attacker requirement. An absent source control file with
   delete enabled also needed protection. No network or remote rsync ran.
3. Initially prepended sender-hide/receiver-protect rules survived standalone
   caller reset probes. **That was insufficient evidence:** combined reset plus
   `--include=*` and delete enabled replaced the lock on both interpreters for
   `--include=!`, `--exclude=!`, and include/exclude-from files containing `!`.
   Intermediate final runs: 97 passed, four strict failures (3.11: 2.05s;
   3.12: 2.56s). These confirmed bypasses required an additional admission repair.
   The independently tested `-F` per-directory reset/include file retained the
   protected lock and remains admitted; no speculative ban was added.

## Concrete narrow repairs

`hashing.py:322–339` now explicitly scans a stack of directories with os.scandir,
propagates enumeration and entry-stat errors, classifies entries without
following links, and checks queued/before/after directory identity. Stable
regular files remain lexically ordered. Existing open_path_under_base hashing
at `:348` still performs rooted secure opening; those errors remain unsuppressed.
Public docstring now describes enumeration/read/identity rejection. Installed
AST-safe style fixes normalized three pre-existing comment prefixes.

`sync.py:328–338` adds rooted literal sender-hide and receiver-protect rules for
the active root lock and selected completion marker before caller rules. Marker
wildcard characters `*?[]` are escaped. Lock-disabled calls do not reserve an
inactive lock filename; marker-disabled calls do not reserve a marker filename.
Receiver protection keeps the coordination inode from payload replacement or
deletion. The reserved names are documented metadata, not mirror payloads.
Official [rsync filter documentation](https://download.samba.org/pub/rsync/rsync.1)
defines hide on the sender and protect against receiver deletion; actual local
transfer proofs below validate this implementation rather than relying only on
command construction.

`sync.py:53` and `:288` now reject joined/split `!` reset patterns and external
include/exclude-from rule sources (including their abbreviations) before target
creation, marker mutation or command execution. Exact ordinary --include and
--exclude names are explicitly handled before the generic forbidden-prefix
check, preserving ordinary pattern compatibility. Existing --filter/-f and
destructive/exec-affecting extra-argument rejection remains intact. Public
extra_args documentation records the narrower rule-file admission contract.

Root independently reviewed these changes and authorized the confirmed sync
repair and admission extension. Root owns release fragment and registry changes.

## Meaningful finite regression coverage

New `tests/test_core/test_filesystem_remote_audit.py` includes root/child scan
denial for both fingerprint APIs, sorted hashes checked against hashlib,
directory/file link exclusion, deterministic scan-to-open file/directory
replacement rejection, and explicit root-link resolution compatibility.
Symlink creation capability failures skip only the corresponding host case.

New `tests/test_core/test_sync_remote_process_audit.py` uses independent spawned
processes and real POSIX flock with acknowledged bounded barriers. A first
synthetic transfer holds its lock through actual marker publication; a second
cannot acquire it until publication returns. The second begins transfer with
the marker absent, is killed at that acknowledged boundary, and leaves no success
marker. A third independently acquires the released kernel lock and succeeds.
Synthetic command workers avoid rsync/network for this process proof; actual
marker file publication and kernel locks are real. Every child is joined/killed
in finite cleanup with at most eight-second acknowledgement waits.

Additional actual local rsync cases preserve lock bytes/inode with source control
file present/absent, delete true/false and broad ordinary caller inclusion;
literal bracket/star/question-mark marker names do not exclude nearby ordinary
content and source cannot publish the marker before the helper does. Combined
reset/source cases now reject before transfer and preserve target state; split
reset and abbreviated external-source cases reject before target creation.
The previously failing assertions were kept strict: safe rejection is the
intended new admission behavior, not an xfail or loss of the inode guarantee.

## Final executed evidence and freeze

Final focused command for each env used absolute isolated source ownership:

```text
PYTHONPATH=/tmp/gunz-utils-fix-audit-20261011-672bfb1/src
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 timeout 60 <env>/bin/python -m pytest
  tests/test_core/test_filesystem_remote_audit.py
  tests/test_core/test_sync_remote_process_audit.py
  tests/test_core/test_hashing.py tests/test_core/test_hashing_structured.py
  tests/test_core/test_sync.py tests/test_core/test_audit_sync_timeout_regressions.py
  -q -p no:cacheprovider
```

- `/tmp/gunz-utils-audit-20261008` Python 3.11: **105 passed in 1.44s**, exit zero.
- `-py312` counterpart Python 3.12: **105 passed in 1.40s**, exit zero.
- Pinned Ruff check of both production and both new test files: passed.
- Pinned mypy `--follow-imports=silent --cache-dir tmp/fs-audit-mypy` on those
  four files: passed, no issues in four source files.
- Installed gunz-style with absolute PYTHONPATH, `--no-cache -j 1` on those four
  files: zero violations and warnings. Its authorized style fixer changed
  signatures/import banners/comment prefixes; final pytest/static proofs reran.

Final source and tests are frozen; the last source edit only clarified public
extra_args documentation after passing tests. This record is the only remaining
agent write. Root aggregate/native/packaging/docs gates and integration remain
separate acceptance evidence. No commit, push, external report, real secret/store
operation, network job or main worktree mutation occurred.

## Independent integration follow-up: short-option clusters

Root independently reproduced another actual local scratch-only bypass after
the initial freeze: `extra_args=('-af', '!', '--include=*')` changed the synthetic
target lock inode and bytes to source content. The validator recognized only a
forbidden flag at the start of an argument, allowing clustered lowercase `f`
to clear the reserved rules. Root explicitly authorized this narrow repair and
revoked the previous executable freeze for it; this was not a speculative ban.

Short-option validation now walks clustered flags and rejects case-sensitive
`e`, `f` and `M`. It stops at argument-taking `B`, `T` and `@` so their attached
payload characters are not misinterpreted as flags. Uppercase `F` and ordinary
`-av` remain supported; ordinary pattern/reset/source policies from the earlier
repair remain intact. No remote shell or remote-option command was executed.

Thirteen additional cases prove: `-af`, `-avf`, `-ae` and `-avM` reject before
command execution with target lock inode/bytes and old marker unchanged; six
parser positives preserve ordinary flags and attached payload boundaries; three
actual tiny local rsync transfers with `-av`, `-aF` and `-aB1024` preserve the
target lock inode/bytes and transfer expected ordinary content.

Final rerun of the exact six-module focused command above:

- Python 3.11: **118 passed in 1.67s**, exit zero.
- Python 3.12: **118 passed in 1.61s**, exit zero.
- Pinned Ruff: passed. Pinned mypy: no issues in four owned source/test files.
- Installed gunz-style: zero violations and warnings in four owned files.

Executable freeze is re-established after this repair; only this task evidence
was written afterward. Root's earlier aggregate is retained as historical failed
integration evidence and does not certify this final fingerprint. Root reruns
the final aggregate and handles the separately assigned pickle-import repair.

## Limits and contract choices

Traversal is a best-effort live-tree integrity operation, **not an atomic tree
snapshot or adversarial enumeration confinement guarantee**. Before/after inode
checks detect tested persistent replacements; a transient replacement restored
to the same inode can evade these checks and may expose outside entry names to
enumeration. Existing secure rooted file opening must still reject unsafe file
paths. Concurrent ordinary in-place content changes also require caller snapshot
or filesystem coordination for a coherent whole-tree view. Explicit root symlink
resolution stays compatible; links found below that resolved root are excluded.

Sync guarantees require cooperating callers using the same lock. lock=False,
raw readers ignoring lock/marker lifecycle and external namespace mutation do
not acquire its coordination guarantee. A success marker means the last
completed transfer published it; a killed process after marker publication can
leave that truthful marker even without returning to its caller. Interrupted
transfer before publication must leave it absent. Actual POSIX/local-rsync proofs
do not certify Windows ACL/reparse behavior, remote rsync server compatibility,
network interruption semantics, disk durability after host power loss or all
possible caller option combinations. No package-wide audit-level promotion is
claimed.


## Root alias review after agent freeze
Installed `rsync --help` identifies `-T` as the exact alias of already forbidden
`--temp-dir`. Independent static before-proof accepted `-Tsynthetic-dir` while
rejecting the long spelling. Root corrected the newly added positive test's
incorrect policy assumption: `T` is now forbidden in clusters, including attached
and split values. Ordinary attached block-size values and modify-window remain
accepted; payload parsing stops at B/@. This aligns an existing restriction,
without permitting temporary-file redirection through its short alias.
Root ran the three sync test modules: **63 passed** on Python 3.11 in 2.23s;
Ruff passed. Both interpreter full suites and canonical static checks are covered
by the final root aggregate. The 118-pass agent packet above predates this final
root correction and is not the final snapshot certificate.


## Coordinator integration
All six canonical local gates pass on the frozen corrected snapshot; see the
[completed parent](2026-10-11-remote-audit-repairs.md) and its source fingerprint.
