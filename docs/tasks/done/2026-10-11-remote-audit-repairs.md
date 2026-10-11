# Remote audit branch repairs

Status: complete for scoped local audit and repairs
Branch: fix/audit-bugs-20261011
Baseline: 672bfb1790c0b52e7494ae9ff5171e80fab3a9fc
Execution checkout: /tmp/gunz-utils-fix-audit-20261011-672bfb1

## Baseline evidence
Python 3.11 and 3.12 focused runs: 15 passed, 2 failed. Rebuilt native runs:
89 passed, 2 failed on each interpreter. Both failures reject supported integer
subclasses. Ruff reports seven issues; mypy passes. Independent finite probes
reproduce manifest traversal omission, canonical set instability, copy aliasing,
worker overallocation, and threshold domain inconsistencies.
Evidence: /tmp/gunz-utils-remote-branch-audit-20261011.json.

## Parallel tasks
1. [Concurrency and cache](2026-10-11-remote-audit-concurrency.md).
2. [Serialization and binary](2026-10-11-remote-audit-serialization.md).
3. [Filesystem and synchronization](2026-10-11-remote-audit-filesystem.md).
4. Root: independent diff review, existing regression-file lint, changelog,
   algorithm registry, local static/docs/packaging/full Python/native gates.

## Boundaries and acceptance
Agents own disjoint production modules and new dedicated test files. Shared
configuration, registry and indexes belong to root. No main edits, merge, push,
PR, hosted workflow execution, or changes to the private linter repository.
Use finite scratch-only probes; preserve strict existing tests. Report suspected
issues separately from proven defects, with failure, fix, test command and result.
Record platform and resource-policy limitations explicitly. Completion requires
independent integration review and successful applicable local gates.


## Integration acceptance
All three subsystem packets were independently reviewed; full-suite static
security failure and clustered/alias option gaps prompted narrow repairs before
acceptance. The revised canonical aggregate passes all six gates. Python 3.11
and 3.12 each have 1710 passes/38 justified skips; each asserted native leg has
91 passes and each forced fallback has 60 passes/31 expected native skips.
Ruff/mypy/local style, strict docs and minimal/extras/wheel/sdist isolation pass.
Evidence: [local audit report](../../audits/2026-10-11-comprehensive/local-verification.md).

Input fingerprint: `bd23ab31df2a8fd7d15954cd61c79e7e6693775a189a8f398928daa4fc789cbe`. Completed hierarchy is archived. Existing
Windows/macOS tasks remain active; documented compatibility/resource policies
are accepted limits, not universal memory-leak or security certification.
Local feature checkout only; no main merge, remote push, PR or hosted CI.
