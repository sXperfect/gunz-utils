# gunz-utils comprehensive audit — 2026-10-11

Branch: `fix/audit-bugs-20261011`. Base: `main`.

## Scope and decision
The original handoff below records source inspection. Actual local failures,
repairs and verification are tracked in [local execution evidence](local-verification.md).
Commits alone are not verification. Main remains unchanged; hosted CI is not
used for this branch review.

## Current source-change inventory
- BUG-001: process_map / process_imap no replay after execution errors; static pickle preflight does not guarantee every input is picklable.
- BUG-002: generation-based invalidation of async TTL cache producers.
- BUG-003: env_overrides explicit scalar/nested collision error.
- BUG-004: binary encoder rejects bool/non-int.
- BUG-005: empty process_map/process_imap validates workers/chunksize.
- BUG-006: process_imap bounded batch input; evaluate early-close, threshold, chunksize, and throughput.
- BUG-007: sequential cross-event-loop cache reuse test only; concurrent multi-loop access remains open.
- BUG-008: directory manifest fails closed on secure-open failure.

## Additional inspection findings
- AUD-009 (needs proof): to_jsonable normalizes sets by repr of converted values; test deterministic nested values, equal logical representations, native parity.
- AUD-010 (source contract issue): dict_utils.deep_merge._isolate catches deepcopy failures and returns the original object; mutable aliasing contradicts no-shared-mutable-substructure claim.
- AUD-011 (needs proof): process_imap generator early-close may wait for outstanding process tasks due to ProcessPoolExecutor context-manager shutdown.
- AUD-012 (resource risk): unbounded user-configured threshold and chunksize can cause large prefetch/windows.
- AUD-013 (needs proof): rsync completion-marker correctness across crash/failure and reader contention.
- AUD-014 (verification): native builds, wheels, extras and Python versions.

## Execution requirements
First checkout this branch locally. Record exact HEAD and environment. Run focused regressions first, then entire CI-equivalent gate. Do not enable GitHub Actions as a substitute for local execution. Report actual commands, output, failures, and environment. Preserve original failure reproductions before changing code.

## Acceptance
Each finding receives status: reproduced, disproved, fixed-and-verified, or deferred with documented reason. Track time/memory and platform-specific differences. Independent auditor reviews fixes and confirms no accidental API break before merge.
