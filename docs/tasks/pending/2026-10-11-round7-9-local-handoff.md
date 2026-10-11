# Rounds 7–9 offline verification handoff

Branch: fix/audit-bugs-20261011
Priority: verify Round 6 deep traversal first, then R7-001 total-cleanup deadline, R9-004 Result invariants, R8-004 identity-based mapping keys, R9-002 async predicate hanging behavior. Remaining items are documentation/contract questions.

Tasks:
1. Freeze HEAD and environment; reproduce each claim with deterministic finite input in scratch space.
2. Classify reproduced defect vs intentional contract, record expected API behavior.
3. Implement only confirmed fixes on feature branch with regression tests.
4. Run Python 3.11 and 3.12, native/pure-Python parity where relevant, lint/mypy, canonical local gate.
5. Update verification evidence and audit registry; independent audit before main merge.

Avoid actual fatal signal delivery in test runner: isolate in subprocess. Do not activate hosted CI. Do not treat unexecuted OSes as verified.
