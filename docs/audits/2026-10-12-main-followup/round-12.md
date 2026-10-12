# Round 12: main v1.14.2 static audit

Base: `main@708399cf52cf86e20e10aa4a016e925667eb47c5`.
Remote source inspection only; no runtime executions or claims of CI verification.

## Source provenance
The latest `main` commit is a release commit updating version/changelog/fragments, not a code-remediation commit for Round 10–11. Earlier audit notes are merged; the reviewed production code still shows the specified behavior. Treat issue closure as unverified rather than presuming prior audit documentation implies repair.

## R12-001 — rate-limiter extreme-rate arithmetic (medium; needs local reproduction)
`src/gunz_utils/rate_limit.py:AsyncRateLimiter.acquire` computes `wait = (tokens - self._tokens) / self.rate`. Inputs are finite positive floats, but tiny positive rates (e.g. `5e-324`) can yield infinite calculated sleep intervals for a finite token deficit; `acquire(timeout=None)` may then never progress, and an overflow may occur on certain arithmetic paths. The refill product `elapsed * self.rate` may also overflow to infinity with very large rates, though capacity caps it.

Reproduce in a short bounded task using a tiny rate and capacity 1; acquire one token then attempt another, wrap in `asyncio.wait_for` so the probe is finite. Validate computed wait and verify timeout-enabled path behavior. Decide whether representability constraints or saturating calculations should be adopted; add tests at floating-point boundaries.

## R12-002 — recursive DAG traversal remains (carry-forward)
`src/gunz_utils/dag.py:WorkflowDAG._topological_order.visit` and `effective_fingerprint.resolve` still recurse. This was documented in R11-002; investigate on a finite 1500-stage chain. Do not count as a new issue.

## R12-003 — safe_float overflow remains (carry-forward)
`src/gunz_utils/parsing.py:safe_float` catches ValueError/TypeError, but not OverflowError from `float(10**10000)`. This was R11-001; reproduce and fix with a regression.

## R12-004 — lease preflight ordering remains (carry-forward)
`src/gunz_utils/leases.py:run_with_lease_heartbeat` schedules the operation before the initial renewal task. See R10-001; verify with task-start event before mutation.

## R12-005 — tcp_reachable timeout is per-connect, not whole lookup (low; contract)
`src/gunz_utils/network.py:tcp_reachable` calls synchronous `getaddrinfo` without an overall deadline and then tries resolved addresses sequentially using `socket.create_connection(timeout=timeout)` for each. Therefore the total call duration can exceed requested `timeout`. Decide whether timeout should mean per attempt or end-to-end; note blocking DNS cannot be made strict merely by changing socket timeout.

## Local verification
- Freeze HEAD and compare with report.
- Reproduce high-priority issues using bounded finite tests.
- Record intended contracts before remediation.
- Run local Python 3.11/3.12 focused + full regression, native/fallback, lint/typing, docs and package gates.
- Do not merge to main, create PR or activate hosted CI until explicitly authorized.

Status: Findings collected, no production code changes, no tests executed this round.
