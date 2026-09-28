# Method audit protocol

## Purpose

An algorithm audit is not a line-by-line style review. It is a structured
attempt to falsify the implementation's public contract. The auditor starts
from behavior that must be true, derives observable invariants, selects an
oracle that does not merely repeat the implementation, and then constructs
tests around the points where the contract is easiest to violate.

The unit of audit is a **method**: a function, class operation, parser,
state-machine transition, scheduling rule, numerical transform, or persistence
operation with externally observable semantics.

## Audit sequence

### 1. Inventory and risk classification

Record the public unit, its callers, state it mutates, external resources it
touches, and the consequences of an incorrect result. Assign higher proof
priority to code involving numerical limits, security boundaries, persistence,
concurrency, process lifecycle, graph traversal, serialization identity, and
resource accounting.

### 2. Write the contract before judging the code

For each method state:

- accepted input types and ranges;
- whether booleans are valid where Python also treats them as integers;
- finite-value requirements for floating-point parameters;
- output shape, ordering, determinism, and units;
- mutation and aliasing behavior;
- error types and whether failure is atomic;
- timeout, cancellation, and cleanup behavior;
- asymptotic or explicit resource bounds.

A test is weak when it proves behavior that was never declared.

### 3. Build a parameter-domain table

Every parameter with semantic restrictions gets a table entry.

| Question | Examples |
|---|---|
| Type domain | integer only, real numeric, path-like, mapping |
| Lower/upper bound | positive, non-negative, uint64 |
| Finiteness | reject NaN and positive/negative infinity |
| Zero semantics | valid identity, disabled feature, or error |
| Boolean semantics | explicitly accepted or rejected |
| Coupled constraints | min <= max, capacity >= request |
| Units | seconds, bytes, items, iterations |
| Extreme magnitude | largest finite float, huge exponent, max integer |

The implementation must validate before mutating durable or shared state.

### 4. Derive invariants

Invariants are properties that must hold for many inputs, not individual
examples. Typical invariants include:

- topological output places every dependency before its consumer;
- decode(encode(x)) == x over the entire supported value domain;
- token count never exceeds capacity and never becomes negative;
- failed budget consumption does not increment usage;
- canonical serialization maps one logical value to one representation;
- an atomic publication never exposes a temporary filename as the target;
- cancellation releases permits and does not leave orphan tasks or processes.

### 5. Select an independent oracle

Preferred oracle order:

1. closed-form mathematics or a standard definition;
2. a standard-library implementation with independently maintained code;
3. an intentionally simple reference implementation;
4. exhaustive enumeration of a small finite domain;
5. round-trip or inverse relation when encode/decode are independently useful;
6. differential comparison between two maintained backends;
7. metamorphic relations when no exact expected value is available.

Do not use a copy of the production algorithm as its own oracle.

### 6. Cover boundary and adversarial cases

At minimum consider:

- empty and singleton inputs;
- exact lower and upper bounds;
- one step below and above every bound;
- duplicate, repeated, or aliased values;
- negative and zero values;
- NaN and infinity where floats are accepted;
- very large but finite values;
- ties and unstable ordering;
- malformed, truncated, overlong, or non-canonical encodings;
- cycles and extremely deep graphs;
- partial reads/writes and short-lived processes;
- timeout, cancellation, simultaneous completion, and retry exhaustion;
- injected I/O, rename, fsync, allocation, and cleanup failures.

### 7. Check numerical behavior separately from type validity

Numerical review asks whether mathematically valid inputs remain meaningful in
machine arithmetic. Inspect intermediate expressions for overflow, underflow,
catastrophic cancellation, division by zero, unstable variance calculations,
NaN propagation, ambiguous quantile conventions, and zero-baseline relative
changes.

A finite-input check is not sufficient if an intermediate operation can still
overflow before a later clamp is applied.

### 8. Check state and failure atomicity

For stateful methods, write the state transition table. For every transition
test both success and failure paths. On failure, identify which state changes
are allowed to remain visible.

For resource-owning methods explicitly test cleanup when an operation fails
after acquisition or launch.

### 9. Check boundedness and complexity

A parameter named `max_*`, `limit`, or `capacity` must bound the resource
it claims to bound. A post-capture size check is not a memory bound. A timeout
checked only after work finishes is not an execution timeout.

Record any gap between the API name and the actual guarantee.

### 10. Convert every finding into a regression test

A correctness fix is incomplete until the smallest reproducible failing case is
encoded as a test. Prefer deterministic tests. If randomness is needed, pin the
seed and report it in the failure message.

## Evidence levels

- **A0 — inventory:** method is known but no correctness claim is made.
- **A1 — reviewed:** contract, parameter domain, invariants, and implementation
  have been reviewed.
- **A2 — encoded evidence:** A1 plus maintained proof/regression tests.
- **A3 — executed proof:** focused proof tests were actually executed
  successfully against the audited revision.
- **A4 — repository gate:** A3 plus the complete canonical local/hosted
  verification gate passed on the same revision.

Documentation or unexecuted test code can never justify A3 or A4.

## Required audit record

Each registry entry should be supportable by a record containing:

1. method or family ID;
2. public units and implementation paths;
3. risk classification;
4. parameter-domain table;
5. invariants;
6. independent oracle;
7. special/adversarial cases;
8. complexity and resource-bound analysis;
9. state/failure-atomicity analysis when relevant;
10. test paths and exact focused command;
11. unresolved limitations;
12. highest evidence level actually achieved.

## Review rule

When implementation and documentation disagree, first decide which behavior is
the intended public contract. Do not silently change one to match the other.
Record the decision in tests and user-facing documentation where the distinction
matters.
