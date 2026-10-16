# Task Index

Active and pending work for `gunz-utils`. Task-record conventions are described
in [`docs/tasks/README.md`](tasks/README.md); completed work is indexed in
[`docs/TASKS_ARCHIVE.md`](TASKS_ARCHIVE.md).

| Task ID | Date | Description | Status |
|:---|:---:|:---|:---:|
| ALGORITHM-2026-09-28 | 2026-09-28 | [Repository-wide algorithm proof program](tasks/active/2026-09-28-algorithm-correctness-audit.md) | Active — remaining proofs/limitations |
| INPUT-ADMISSION-2026-10-08 | 2026-10-08 | [Fixed key/salt input admission](tasks/pending/2026-10-08-fixed-key-input-admission.md) | Pending; compatibility contract first |
| PLATFORM-2026-10-08 | 2026-10-08 | [Native Windows/macOS verification](tasks/active/2026-10-08-platform-verification.md) | Active; native hosts pending |
| NP-01 | 2026-10-08 | [Windows readiness and contracts](tasks/active/2026-10-08-platform-windows.md) | Preparation complete; native host pending |
| NP-02 | 2026-10-08 | [macOS readiness and contracts](tasks/active/2026-10-08-platform-macos.md) | Preparation complete; native host pending |
| NP-03 | 2026-10-08 | [Portable platform verifier](tasks/active/2026-10-08-platform-verifier.md) | Linux preparation verified; native hosts pending |
| NP-04 | 2026-10-08 | [Async pipe deadline follow-up](tasks/active/2026-10-08-platform-async-drain.md) | Repaired and integrated on Linux; native proofs pending |

The [2026-10-17 audit network, dict, streaming fixes](tasks/done/2026-10-17-audit-network-dict-streaming-fixes.md)
are complete; tcp_reachable cumulative deadline bounding across multiple resolved IPs,
dict_utils.deep_merge max_depth recursion guards, streaming.iter_jsonl max_line_length
memory protections, and ext/project_* same-line GS007 suppressions are verified across
all 1782 unit tests, native extension compilation, and local gates.

The [2026-10-16 audit correctness repairs](tasks/done/2026-10-16-audit-correctness-repairs.md)
are complete; safe_float overflow/bool rejection, iterative DAG and provenance
graph traversals, rate-limiter numerical bounds, and redaction parameter validation
are verified across all 1774 unit tests and native extension builds.

The [2026-10-08 follow-up audit and repairs](tasks/done/2026-10-08-audit-follow-up.md)
are complete for the stated scope; all six canonical gates passed. Detailed
review/repair records are listed in the task archive.

The repository-wide algorithm program remains active for documented deeper
proof obligations; completed scoped repairs do not erase accepted limitations.

The [cross-process storage proofs and approved mode-switch recovery repair](tasks/done/2026-10-08-storage-process-proofs.md) are also complete for the stated scope; all six canonical gates pass.

The [2026-10-11 remote branch review](tasks/done/2026-10-11-remote-audit-repairs.md)
is locally verified on its feature branch; integration into main remains separate.

The [round-five remote cache fix verification](tasks/done/2026-10-11-round5-local-verification.md)
passes all six local gates on the subsequently fetched feature-branch snapshot.

The [rounds 6–9 offline audit](tasks/done/2026-10-12-offline-rounds6-9.md)
is complete for its stated Linux scope; native-host and pre-merge review limits
remain explicit.
