# Local-agent handoff: gunz-utils audit and verification

Status: pending
Repository: sXperfect/gunz-utils
Branch: fix/audit-bugs-20261011

## Task A — Baseline (critical path)
- Record branch HEAD, Python/compiler/OS environment, and worktree status.
- Reproduce each existing test failure before applying additional patches.
- Execute focused regressions for BUG-001..008, then canonical suite.
- Check lint, typing, native modes, wheel/sdist reproducibility.
- Archive command lines, exit codes, logs, and failure classification.

## Task B — Concurrency + caching (after A)
- Confirm no replay after process failure and no duplicate iterator output.
- Verify ordering, bounded windows and source consumption.
- Profile process_imap throughput against main and quantify early-close blocking.
- Test concurrent independent event loops and cancellation with async_ttl_cache.
- Fix only after a reproducible test. Keep backward compatibility unless a documented contract update is approved.

## Task C — Serialization + native parity (after A; parallel to B)
- Validate canonical JSON stability, collection normalization, binary boundaries and native/Python parity.
- Reproduce aliasing caused by deep_merge fallback on uncopyable mutable objects.
- Decide between error on copy failure and explicit narrowed isolation contract.

## Task D — Filesystem + synchronization (after A; parallel to B and C)
- Verify directory_manifest fail-closed behavior, symlink treatment, race handling.
- Exercise atomic file writes and transactional directory behavior on supported platforms.
- Verify rsync completion marker with interrupted transfers and lock contention.
- Do not use privileged or destructive tests outside scratch directories.

## Task E — Packaging and release (after A; parallel)
- Run supported interpreter/OS matrix, minimal and extras installation, native extension builds.
- Check static/local CI equivalence, version consistency, source distribution contents.
- Preserve the repository policy of local verification; do not activate GitHub Actions.

## Task F — Final auditor integration (after B-E)
- Ensure every finding is reproduced/disproved and triaged.
- Review diffs and tests; rerun the complete local suite.
- Write signed-off audit summary listing known limitations and performance measurements.
- Do not merge or create PR unless explicitly authorized.

## Evidence
See `docs/audits/2026-10-11-comprehensive/README.md` and `verification-matrix.md`.
