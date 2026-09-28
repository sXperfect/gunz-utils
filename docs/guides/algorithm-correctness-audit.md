# Algorithm Correctness Audit Guide

## Purpose

This guide defines the evidence required before an algorithmic implementation in
`gunz-utils` may be called audited. It applies to numerical/statistical code,
graph and traversal algorithms, deterministic selection, hashing/canonicalization,
bounded streaming, state machines, retry/backoff, rate limiting, caches,
concurrency coordination, benchmark calculations, and other code whose
correctness depends on more than direct field plumbing.

The maintained inventory and evidence ledger is
[`docs/audits/algorithm-registry.md`](../audits/algorithm-registry.md).

The durable design-level protocol and reusable proof-test patterns are also
maintained in [`docs/design/audit/`](../design/audit/README.md).

## Audit levels

| Level | Meaning |
|---|---|
| A0 | Inventoried only. No correctness claim. |
| A1 | Implementation reviewed against an explicit contract and invariants. |
| A2 | A1 plus existing tests reviewed against the proof obligations. |
| A3 | A2 plus missing oracle/adversarial/property tests added and focused tests executed successfully. |
| A4 | A3 plus the canonical aggregate verification gate passes on the same audited revision, locally or in hosted CI. |

Do not use "audited" without a level. A0 is not an audit result.

## Required proof packet

Every audited algorithm must have a compact proof packet in the registry or a
linked design note containing all of the following.

### 1. Contract

State:

- accepted input types and shapes;
- output type/shape and ordering guarantees;
- mutation/aliasing behavior;
- deterministic versus randomized behavior;
- error behavior;
- resource or complexity bounds when those are part of the API.

Separate documented behavior from incidental implementation details.

### 2. Preconditions and parameter domains

For every numerical or size/time parameter, record:

| Property | Questions |
|---|---|
| Type | Are booleans allowed as numbers? Are integers required? |
| Finiteness | Are `NaN`, `+inf`, and `-inf` rejected? |
| Bounds | Inclusive/exclusive lower and upper bounds? |
| Zero | Valid value, identity, empty case, disabled behavior, or error? |
| Magnitude | What happens near integer/float representation limits? |
| Units | Seconds, bytes, counts, ratios, fractions, percentages, etc.? |
| Coupling | Must one parameter be smaller/larger than another? |

Validation must happen before state mutation, sleeping, I/O, task creation, or
other externally visible work whenever practical.

### 3. Invariants

Write invariants in a form that can become tests. Examples:

- token-bucket balance stays in `[0, capacity]`;
- topological output orders every dependency before its consumer;
- a failed transactional read restores the original cursor;
- cache size never exceeds capacity;
- canonical serialization is independent of mapping insertion order;
- a bounded writer never reports more committed bytes than the destination
  accepted;
- retained items preserve the specified stable order;
- finite statistical inputs either produce finite representable summaries or
  fail explicitly rather than silently returning overflow artifacts.

### 4. Reference or oracle

Prefer at least one independent oracle:

1. a mathematical closed-form result for small cases;
2. a trusted Python standard-library implementation;
3. a deliberately simple reference implementation;
4. round-trip/inverse properties;
5. exhaustive enumeration for a small finite domain;
6. differential comparison with a standards-defined implementation.

Tests that merely reimplement the production formula line-for-line are weak
evidence and should not be the only oracle.

### 5. Boundary and special cases

At minimum consider:

- empty input;
- singleton input;
- minimum/maximum valid parameter;
- one step outside each valid bound;
- duplicate values/names;
- negative values;
- zero;
- `NaN` and `±inf` for floating-point APIs;
- extremely large finite magnitudes;
- ties and equal priorities;
- cycles/self-edges for graphs;
- partial reads/writes and truncated encodings;
- cancellation, timeout, and simultaneous-completion races for async code;
- unhashable inputs where hashing is optional;
- deterministic behavior across input order/process hash randomization where
  promised.

Only omit a case when it is structurally impossible or irrelevant; record why.

### 6. Numerical analysis

For floating-point/statistical code, review:

- overflow/underflow of intermediate expressions;
- catastrophic cancellation;
- division by zero or near-zero scaling;
- `NaN` comparison behavior;
- accumulation error;
- stable mean/variance algorithms;
- percentile/quantile convention;
- sample versus population denominators;
- deterministic random seeding;
- whether a relative change is mathematically defined for a zero baseline.

Prefer `math.fsum`, `statistics.fmean`, `statistics.stdev/pstdev`, or another
well-defined stable primitive when it is strictly safer than a hand-written
formula and preserves semantics.

### 7. Complexity and boundedness

Record expected time and space complexity for nontrivial algorithms. For
streaming/concurrent code, also prove operational bounds:

- maximum resident buffered items;
- maximum concurrent tasks;
- maximum retries/sleeps;
- whether inputs are materialized;
- whether recursion depth can grow with untrusted input;
- whether a loop has a monotonic progress measure.

### 8. Failure atomicity and state machines

For mutable/stateful algorithms, identify legal states and transitions. Verify:

- invalid input does not partially mutate state;
- cancellation/failure restores or leaves a documented state;
- cleanup runs exactly once where required;
- simultaneous events have a deterministic precedence rule.

## Test patterns

Use a mix of:

- table-driven boundary tests;
- known-answer tests;
- deterministic fuzz/property-style loops using `gunz_utils.testkit`;
- exhaustive small-domain tests;
- metamorphic tests (permutation invariance, scale/translation relations where
  mathematically valid);
- fault injection;
- async race/cancellation tests with controlled clocks/events;
- cross-implementation differential tests.

Keep tests deterministic. Hypothesis may be used during investigation, but the
repository must not acquire it as a core runtime dependency.

## Numerical parameter checklist

Before an A3/A4 result, explicitly test these values when applicable:

```text
-1, 0, smallest valid positive value, ordinary value, upper boundary,
one past upper boundary, NaN, +inf, -inf, very large finite value
```

For integer count parameters also test `bool` because `bool` is a subclass of
`int` in Python. Accepting it must be deliberate.

## Audit workflow

1. Add the algorithm/family to the registry at A0.
2. Read implementation, public docs, call sites, and existing tests.
3. Write the contract, parameter domains, invariants, oracle, and complexity.
4. Move to A1 only after the implementation review is complete.
5. Compare existing tests with every proof obligation; move to A2 only when
   evidence is linked.
6. Add missing adversarial/oracle/property tests and fix defects discovered.
7. Run the focused test module(s); move to A3.
8. Run `./scripts/verify.sh` locally or the equivalent hosted `scripts/audit_ci.py` aggregate gate on the same audited revision; move to A4 only when every gate passes.
9. Add/update the changelog fragment for observable behavior changes.

## Review rule for new algorithms

Any new algorithmic public API should add or update a registry entry in the same
change. New numerical parameters must document finiteness and boundary semantics
even when the implementation relies on Python's dynamic typing.
