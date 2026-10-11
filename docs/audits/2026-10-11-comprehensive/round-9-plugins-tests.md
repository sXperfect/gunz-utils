# Round 9 — plugins, test helpers and API contracts (remote source audit)

## R9-001 — Plugin discovery does not isolate BaseException (contract check)
`plugins.discover_plugins` catches `Exception` during `entry_point.load()` and optional construction. A plugin raising `KeyboardInterrupt` or `SystemExit` escapes, contrary to a very broad interpretation of failure isolation. This is often *correct* (do not swallow shutdown/cancellation). Document explicit exception policy, do not broaden catch speculatively.

## R9-002 — eventually_async predicate timeout is cooperative (low, contract)
`testing.eventually_async` checks the clock only after awaiting predicate. A never-returning predicate defeats the configured timeout; equivalent synchronous `eventually` cannot preempt a blocking predicate. Test and document whether timeout applies to polling duration only or to each predicate invocation.

## R9-003 — temporary_env cannot be safely nested across threads (low, known global-state limitation)
`testing.temporary_env` saves and restores process-global `os.environ` without a lock. Concurrent contexts modifying the same key can interfere. Existing intended scope likely single-threaded test fixtures; clarify limitation.

## R9-004 — Result dataclass constructor permits inconsistent state (medium, contract)
`result.Result` exposes public dataclass initialization with independent `value`, `error`, `_ok`. Callers can directly construct `Result(value=1,error='oops',_ok=True)`, despite the class docstring claiming exactly one success or error. Consider __post_init__ validation or document factories-only convention; explicit None-valued success/error must remain valid.

Remote inspection covers targeted modules, not proof of entire 97-module package. Stop before invasive fixes pending local tests.
