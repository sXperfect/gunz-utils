# Round 7 — lifecycle, signals and context (remote source audit)

Reference: fix/audit-bugs-20261011, after Round 6. Source inspection only.

## R7-001 — GracefulShutdown.run_cleanup timeout is per callback (medium, source-confirmed)
`signals.py:GracefulShutdown.run_cleanup` applies `asyncio.wait_for(res, timeout=self.timeout)` individually to each awaited callback, inside a LIFO loop. N callbacks can consume ~N × timeout, while class documentation says maximum timeout to wait for async cleanup callbacks. Synchronous callbacks are not time-bounded at all.

Local regression: register 3 coroutine callbacks each waiting longer than timeout; compare elapsed time against timeout vs 3×timeout. Clarify whether policy is total deadline or per-callback timeout; if total, compute monotonic deadline and pass remaining time to each await. Document nonpreemptible synchronous callbacks.

## R7-002 — Timer.stop before start records an end time (low, source-confirmed)
`timing.py:Timer.stop` sets `_end_time` even when `_start_time is None`. Construct `Timer(auto_start=False)`, call `stop()`, and inspect transition into context manager. `__enter__` starts and clears the stop timestamp so context-manager use may be fine, but manual stop/start state should be specified rather than inferred.

## R7-003 — Async signal restoration overwrites changed handlers (medium, contract/race)
`AsyncSignalRegistration.restore` unconditionally sets previous process handler after removing loop handler. If other code changes the handler during registration, restoring overrides that newer registration. Require ownership model or explicit contract test. Signal tests must run in isolated subprocesses and on actual supported OSes.

## R7-004 — operation_context empty value silently creates ID (low, contract)
`operation_context` uses `value or uuid`, so explicit empty string is treated as absent. Determine whether empty identifiers are invalid or intentionally generated; document and test.

No production changes this round. Recommended local owner: lifecycle/signals agent.
