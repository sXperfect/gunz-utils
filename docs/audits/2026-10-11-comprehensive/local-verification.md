# Local execution and repair evidence

## Scope and baseline
Review began at `672bfb1790c0b52e7494ae9ff5171e80fab3a9fc` on
`fix/audit-bugs-20261011`, descended from `main@a375ed7` by 13 commits.
All work uses an isolated checkout; main and hosted CI are unchanged.
This is a scoped branch review, not a new certification of every package module.

Linux, Python 3.11.14 and 3.12.13; primary pytest 9.0.3, Ruff 0.14.10,
mypy 1.19.1. The local private style checker is installed from its published
revision `7d1866e6128d08c3c37010833c554d1814b673ab`, with checked-out
utils source supplied explicitly. Its hosted skip remains in place.

Before repairs, the new branch regressions plus strict native safety suite gave
15 passes and two failures on each interpreter. Actual rebuilt native proof
suites gave 89 passes and the same two failures on each interpreter: supported
integer subclasses were rejected. Ruff found seven issues; mypy passed.
Baseline log paths and independent reproductions are retained under
`/tmp/gunz-utils-remote-branch-audit-20261011.json` and corresponding
`/tmp/gunz-utils-remote-audit-*-20261011.*` logs.

## Independent observations before repair
- A finite nine-item stream requested 128 automatic workers when CPU count was
  mocked to 128. No real 128-process pool was started.
- Allowed large thresholds overflowed the C-sized `islice` stop; eager mapping
  accepted invalid thresholds and consumed input before validation.
- A simulated child-directory `scandir` permission error produced a successful
  empty manifest, omitting an existing file.
- Equivalent hashable mappings inside sets produced different canonical JSON
  when mapping insertion order changed.
- Uncopyable mutable leaves retained identity in `deep_merge`. An existing test
  explicitly requires this fallback; public documentation overstates isolation.
- Closing an iterator after one result waited about 0.351 seconds for a finite
  outstanding worker and left zero child processes. This is shutdown latency,
  not evidence of a memory or process leak.

## Integration result
The first full aggregate passed release, lint, strict docs and packaging, but
both interpreter test legs failed the unchanged security import guard: one
failure, 1674 passes and 38 skips per interpreter. The direct pickle preflight
import introduced by the remote branch is incompatible with that guard; the
corrective encoder uses multiprocessing semantics without relaxing the guard.
The revised full aggregate passes all six gates. Child evidence records
are linked from the [completed parent task](../../tasks/done/2026-10-11-remote-audit-repairs.md).

## Finding disposition after focused repair verification

| ID | Disposition and evidence |
|---|---|
| BUG-001 | No replay confirmed for real user failures and abrupt worker death; input-iteration errors propagate. |
| BUG-002 | Generation invalidation retained and verified with blocked producers and cancelled waiters. |
| BUG-003 | Scalar/nested conflicts raise in both orders; shared root packet 27 passes plus 22 subtests. |
| BUG-004 | Integer-subclass compatibility repaired; bool/nonintegers still fail. Both actual-native expanded packets: 152 passes. |
| BUG-005 | Options now validate before source consumption, including empty inputs. |
| BUG-006 | Streaming windows retained; automatic workers capped by observed work; large integer lookahead overflow repaired. |
| BUG-007 | Concurrent pending work requires one live loop; cross-thread rejection and producer completion tested. |
| BUG-008 | Enumeration/stat/open errors propagate; link and replacement cases preserve secure-opening checks. |
| AUD-009 | Canonical set ordering repaired using normalized JSON keys; supported nested mappings tested. |
| AUD-010 | Public documentation corrected; uncopyable-leaf identity is an accepted tested compatibility limit. |
| AUD-011 | Finite early-close wait observed; running arbitrary callables have no imposed termination deadline. |
| AUD-012 | Configured lookahead/window bounds documented; large caller budgets and eager process_map remain caller responsibilities. |
| AUD-013 | Metadata protection and reset admission repaired; real local rsync plus bounded spawn crash/contention proofs pass. |
| AUD-014 | Linux interpreter/native/fallback and isolated artifact checks executed; Windows/macOS deferred to existing native-host tasks. |

Recorded child packets across the repair iterations pass on both interpreters:
final concurrency **95 plus 11 subtests**, serialization **152 native / 121
fallback plus 31 expected skips**, and filesystem/sync **118** before the last
root alias correction. Root then ran **63** sync regressions, and the final full
interpreter gates cover the corrected snapshot. These packets establish focused
A3 evidence; final aggregate integration is recorded separately below and does
not certify unexecuted hosts.

A finite 1,000-item, two-worker `abs` observation before the final encoder
follow-up compared main with the feature:
0.0202s versus 0.2525s and 716145 versus 156643 peak traced parent bytes. The
bounded windows reduce retained parent data at a throughput cost for tiny calls.
This is a single observation, not a benchmark guarantee or total-process RSS.

## Synchronization review extension
Actual scratch-only local rsync reproduced replacement of the held coordination
lock by a same-named source file. Rooted sender-hide and receiver-protect rules
reserve active metadata. Independent review required combined rule-reset plus
include-all probes: initial reset-only negative results were insufficient, and
the combined probes reproduced a bypass. The repair rejects those reset
rules (joined or split arguments) and external include/exclude rule sources,
including their abbreviations, before filesystem mutation. Ordinary rules and
tested per-directory filters remain supported.
No public issue, remote transfer or production directory was involved.

## Additional integration findings
- AUD-015: direct pickle import violates the existing static security contract;
  a registered multiprocessing reducer also disproves plain-pickle preflight
  equivalence. The repair uses multiprocessing ForkingPickler encoding and imports only the
  standard-library PicklingError exception type. The original guard is unchanged;
  independent AST checks forbid decoder APIs. Registered reducers now execute
  real workers, while resource failures and cancellation retain their identity.
  Updated focused packet: 95 passes plus 11 subtests per interpreter.
- AUD-016: a root-executed three-second local-only synthetic regression proved
  clustered rsync filter options can reset metadata protections. Clustered
  forbidden flags now reject before target mutation. Root also aligned the short
  temporary-directory alias with the existing long-option restriction, using
  the installed rsync help as the independent alias oracle. No network or shell
  was used. Root sync regression packet after that correction: 63 passes.

## Additional contract review
Case-normalized scalar environment aliases retain existing last-entry precedence
(`APP_DB` and `app_db`); BUG-003 specifically repairs scalar/nested path
conflicts. A broader duplicate-alias rejection policy is deferred because it
would change accepted precedence behavior. A mechanical AST scan inspected all
97 Python source modules for direct dynamic execution, unsafe deserialization,
implicit shell calls and production assertions, with no matches in those
specific categories. This scan does not replace manual trust-boundary review.

## Accepted limits
Windows/macOS execution still requires native hosts; Linux simulations do not
close that proof gap. User-configured streaming thresholds/chunksizes control
prefetch budgets. Deep merge cannot promise isolation of leaf objects whose
copy protocol fails while preserving the supported fallback. A directory
manifest is not an atomic snapshot of a concurrently changing directory tree.


## Final local acceptance

Coordinator reviewed the disjoint source diffs, preserved the original strict
security/native tests, independently reproduced the clustered-option and short
alias issues, and checked that verification inputs remained frozen.

```bash
PYTHONPATH=/tmp/gunz-utils-fix-audit-20261011-672bfb1/src \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /tmp/gunz-utils-audit-20261008/bin/python \
  scripts/audit_ci.py \
  --compat-python /tmp/gunz-utils-audit-20261008-py312/bin/python \
  --summary-json /tmp/gunz-utils-remote-repair-integrated-summary.json
```

| Gate | Actual result |
|---|---|
| Release metadata | PASS; existing untagged-version/next-patch advisories remain |
| Ruff / mypy / local gunz-style | PASS; 97 typed source modules; zero style violations, 99 advisory warnings |
| Python 3.11 | 1710 passed, 38 justified skips; native fallback 60 passed/31 skips; actual native 91 passed |
| Strict Sphinx | PASS |
| Isolated packaging | PASS; minimal/extras imports, installed wheel/sdist origins and py.typed verified |
| Python 3.12 | 1710 passed, 38 justified skips; native fallback 60 passed/31 skips; actual native 91 passed |

The 38 ordinary-suite skips comprise 31 native-only cases exercised by the
separate actual-native leg and seven actual Windows/macOS cases awaiting native
hosts. The benchmark deprecation warning remains an expected compatibility
warning. No test was weakened or marked xfail to hide a discovered failure.

Full log: `/tmp/gunz-utils-remote-repair-integrated-gates.log`.
Failed first aggregate and its logs remain preserved separately for provenance.
Verification input fingerprint (302 source/test/configuration/build/docs-source
and release-fragment files): `bd23ab31df2a8fd7d15954cd61c79e7e6693775a189a8f398928daa4fc789cbe`.

This establishes scoped Linux integration evidence. Unexecuted host proofs,
uncopyable-leaf aliases, live-tree snapshot limits, single-live-loop ownership,
caller-selected budgets and measured streaming throughput costs remain explicit.
Main is unchanged; no merge, push, PR, hosted run or release was performed.
