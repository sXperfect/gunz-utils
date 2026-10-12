# Round 10 — main branch static audit (2026-10-12)

Base: `main@af4bcbfef7f57629511b26513084caed5803bb52`.
Purpose: new issues independent of locally verified Rounds 6–9. This is **source inspection**, not a rerun of the test suite. The baseline local evidence is in `docs/audits/2026-10-11-comprehensive/2026-10-12-offline-verification.md`.

## R10-001 — immediate renewal does not gate operation startup (medium; source-grounded)

File: `src/gunz_utils/leases.py`, `run_with_lease_heartbeat`.
With `renew_immediately=True`, the operation task is scheduled first using `asyncio.ensure_future(operation())`, and then the heartbeat task is scheduled. The immediate renewal is executed inside the heartbeat coroutine, which can run after the operation has begun. The lease-owning preflight therefore does not actually gate work execution. A side-effecting operation can start despite `renew()` returning False.

Local reproduction: operation sets an `asyncio.Event` before its first await, renewal checks the event and returns False; assert whether work began. Also test renewal exceptions and cancellation without leaking tasks. Fix proposal: await initial renewal *before scheduling the operation*, then create periodic heartbeat with `renew_immediately=False`. Preserve cancellation/exception propagation.

## R10-002 — configured retry timeout does not prohibit initial execution after deadline (medium; contract-dependent)

File: `src/gunz_utils/retry.py`, `run_with_retry` and `async_run_with_retry`. Both set `deadline = _deadline(policy.timeout)` and immediately invoke the first operation; deadline checks apply only when deciding whether to sleep/retry. Under `timeout=0`, the operation still runs once. An operation that runs beyond the deadline can return successful output. Decide whether timeout means overall deadline, or only retry scheduling budget; document whichever contract is retained.

Local reproduction: policy with `timeout=0`, operation increments a counter; inspect result. Also measure slow successful operation and retry_if_result semantics. Do not claim hard preemptive timeout without an executor / cancellation mechanism.

## R10-003 — JSON Lines parser has no byte/record ceiling (resource/security policy review)

File: `src/gunz_utils/streaming.py`, `iter_jsonl`. Iteration is lazy per line, but `json.loads(line)` parses a whole caller-supplied line without a size, nesting or item budget. A very large record can consume substantial resources. Consider optional `Limits` integration if the function is used on untrusted streams; document that the caller must bound incoming data otherwise. Not a confirmed bug if inputs are trusted.

## R10-004 — captured writer failures leave partial destination writes (contract review)

File: `streaming.py`, `BoundedWriter` and `DigestWriter`. Both account for successful partial writes and raise if the underlying handle stops making progress. This preserves accurate counters but does not roll back partial destination writes, so caller may observe a partial file after a failure. This is normal streaming semantics; test and explicitly document atomicity expectations. Do not automatically change behavior.

## Offline agent work
1. Reproduce R10-001 with event-synchronized tasks; determine expected guarantee for immediate lease renewal and add test.
2. Resolve R10-002 timeout contract before code changes.
3. Identify untrusted callers of `iter_jsonl` and determine whether bounds belong in API or caller.
4. Run the existing lease/retry/streaming test suites plus the full local gates on any changes.
5. Keep `main` unchanged pending verified repairs; no hosted CI on the audit branch.

## Status
Source-level findings only; no code fixes or test results from this round.
