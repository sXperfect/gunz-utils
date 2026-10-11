# Round-five remote fetch and local verification

Status: complete for scoped local verification
Fetched branch: fix/audit-bugs-20261011@d94adfe
Prior verified snapshot: 2c04aa6

## Scope
Verify the new synchronous generation invalidation fix, debug local gate failures,
and resolve R5-002..004 contract questions without inventing threading guarantees.
Main and hosted workflows remain unchanged; the private style checker runs locally.

## Evidence and acceptance
Independent before/after stale-result probe reproduces the remote fix's purpose.
New style failure is corrected; both interpreters pass 80 focused tests and 65
subtests. Five new finite tests cover multiple clears, old errors, independent
misses and cooperative deadline exception behavior. Cache and budget public
contracts are clarified; required release fragment added. All six canonical local gates pass. Both Python versions have 1716 passes/38
justified skips; native legs each pass 91 tests and fallback legs pass 60 with
31 expected native-only skips.
Details: [round-five audit](../../audits/2026-10-11-comprehensive/round-5-static-followup.md).

Frozen input SHA256 (304 files): `f7615473b8c32f494e89fc1f28ede57f138d1cf9c56f2a224d8d41c095a68f80`.
Main remains unchanged; actual Windows/macOS proof tasks remain open.
