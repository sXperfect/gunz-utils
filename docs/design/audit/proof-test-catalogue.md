# Proof-test catalogue

This catalogue maps algorithm shapes to reusable test designs. It is a starting
point, not a substitute for a method-specific contract.

## Pure deterministic transforms

Use table-driven boundary cases plus metamorphic properties. Verify
determinism, non-mutation of inputs, ordering rules, duplicate handling, and
round-trip relations where an inverse exists.

## Numerical methods

Compare against closed-form values or the Python standard library when
possible. Test zero, singleton, symmetric data, large finite magnitudes,
representable extremes, unrepresentable results, NaN, infinity, booleans, and
parameter values immediately around every bound.

## Encoders and parsers

Use known-answer vectors, exhaustive small-domain round trips, malformed and
truncated vectors, non-canonical alternatives, maximum-width values, and
transactional cursor/state rollback on failure.

The varint audit uses exhaustive round trips over 0 through 65535 plus explicit
uint64 boundary and malformed vectors.

## Graph algorithms

For small node counts, enumerate every directed graph and use an independent
cycle/topology oracle. For accepted DAGs verify that every edge points from an
earlier output position to a later one. For rejected graphs verify that state
is not partially published.

The workflow DAG audit enumerates every directed graph on four named nodes
(4096 edge sets) and compares acceptance against a Kahn-style oracle.

## Stateful rate, retry, cache, and breaker algorithms

Drive the state machine with a fake clock. Assert conservation/capacity
invariants after every transition. Exercise exact threshold crossings,
timeouts, recovery, repeated failure, success after recovery, and invalid
parameters before the first mutation.

## Concurrency algorithms

Prefer deterministic synchronization primitives over sleeps: barriers, events,
controlled futures, and injected clocks. Test cancellation before acquisition,
during ownership, and during release; simultaneous completion; exception
propagation; bounded queue/permit counts; and absence of leaked tasks.

## Filesystem and persistence algorithms

Use temporary directories plus injected failures around write, flush, fsync,
rename, directory fsync, copy, and cleanup. Check both visibility and
durability contracts. For content-addressed stores, add concurrent writers of
identical and distinct content.

## Process and subprocess algorithms

Test launch failure, timeout, termination escalation, child cleanup, partial
output, huge output, process exit between observations, and platform parser
vectors. Distinguish a post-capture output-size check from a true streaming
memory bound.

## Differential optional backends

Run the same input corpus through the dependency-free and optional
implementations and compare externally promised behavior. Differences that are
intentional must be documented explicitly rather than normalized away in the
test.

## CI/orchestrator tests

Treat CI code as production code. Unit tests should prove that:

- independent gates continue after failures;
- fail-fast remains available for local diagnosis;
- all gate return codes are represented in the summary;
- a failing gate makes the final process fail;
- summary files are valid and created before final exit;
- compatibility failures are independent of primary-gate failures.

These tests prevent the verification system itself from silently hiding
failures.
