# Rounds 6–9: local audit and repairs — 2026-10-12

## Snapshot and boundaries
Pulled `fix/audit-bugs-20261011@af0366fbeabe584f471b2f7fa68d27d4db563df7`
into the clean isolated feature checkout. Five remote commits changed only four
static audit notes and their pending handoff. Main remains `a375ed7`.
Linux Python 3.11.14/3.12.13, pytest 9.0.3, Ruff 0.14.10 and mypy 1.19.1.
Installed private gunz-style ran locally; hosted workflow settings are unchanged.

Code probes, test runs and artifact installs used local tools and synthetic data.
One initial Sphinx CLI run used an unsupported dictionary override and attempted
an external Python documentation inventory fetch. It failed strict verification
and is excluded from accepted results. The corrected and final builds pass an
actual empty dictionary through Sphinx's Python API, preventing inventory fetches.
No dependencies were downloaded; no hosted CI, main merge, push or release ran.

## Reproductions and narrow repairs
Before production edits, the dedicated 15-case suite gave **10 failed, 5 passed**.
Finite baseline JSON: `/tmp/gunz-utils-offline-rounds6-9-baseline.json`.
Failure log: `/tmp/gunz-utils-offline-rounds6-9-before-tests.log`.

| Finding | Disposition |
|---|---|
| R6-001 | Fixed: deep_diff uses an iterative, lazy depth-first stack; 1500-level input succeeds, cycle/pair handling and report order remain compatible. |
| R6-002 | Fixed: freeze_structure assembles standard containers iteratively and rejects active cycles; deep input, shared nodes and empty siblings tested. |
| R6-003 | Explicit str flattening is bounded by existing cycle/nesting checks; defaults still treat strings as scalars. Contract clarified. |
| R6-004 | Value comparison with visited container pairs, not graph alias-topology comparison. Existing behavior preserved. |
| R7-001 | Per-awaitable timeout retained and documented. Three finite callbacks with timeout .01 took about .0305s. No total or synchronous-preemption guarantee. |
| R7-002 | Stop before start yields elapsed zero; start/context entry resets the stop timestamp. Supported state transitions verified and documented. |
| R7-003 | Isolated actual Linux loop probe overwrites a foreign handler on restore. Registration requires exclusive handler ownership; unrelated/overlapping changes are unsupported. No generic prior loop-callback restoration guarantee. |
| R7-004 | Empty operation ID intentionally generates a UUID; nested outer context is restored. Documented and verified. |
| R8-001 | Expected caller-budgeted bootstrap complexity. Finite 64-observation/64-resample probe: .002079s and 8582 peak traced parent bytes; not total RSS or a large-input guarantee. |
| R8-002 | Fractional unscaled byte magnitudes truncate; negative signs remain. Existing behavior documented. |
| R8-003 | Deterministic key traversal requires stable, distinct representations. Arbitrary custom repr ordering is outside that guarantee. |
| R8-004 | Mapping keys follow defensive deepcopy semantics; identity-based original keys are not interchangeable with copied keys. Runtime behavior preserved and tested. |
| R9-001 | Ordinary plugin exceptions are isolated; BaseException process-control signals propagate. Verified with a caught synthetic SystemExit, without OS signal delivery. |
| R9-002 | Polling is cooperative. Hung-predicate probe is bounded by an outer deadline and verifies cancellation drainage; helper timeout alone is not preemption. |
| R9-003 | Isolated overlapping environment contexts left synthetic value A. Global environment modification requires caller serialization; documentation clarified. |
| R9-004 | Fixed: Result validates boolean variant tags and rejects an inactive non-None payload. None-valued success and error remain supported. |
| Additional cleanup domain | Fixed: NaN/infinite cleanup timeouts reject before instance state is established. |
| Additional cleanup cancellation | Fixed: direct cleanup cancellation propagates and drains the awaited callback; ordinary error collection and LIFO order remain. |
| Additional retention admission | Fixed: invalid retention limits reject before consuming a generator. Negative, bool and fractional bounds have strict regressions. |

The first iterative diff draft queued all sequence children; review replaced it
with lazy iterator frames. A guarded 100000-length sequence proves later items
are not read before the first leaf equality error. Opaque equality/deepcopy hooks
remain caller code, with their own execution/resource behavior. No default depth
cap or incompatible valid-input truncation was introduced.

## Independent oracle and resource evidence
200 seeded finite shallow input pairs match the preceding recursive implementation
for difference fields and frozen values. A single 20-call/100-entry observation:
recursive diff .010436s, iterative diff .014420s; recursive freeze .011206s,
iterative freeze .012363s. This records a shallow-workload overhead tradeoff,
not a benchmark guarantee. Standard deep traversal now avoids Python call-stack
exhaustion; explicit node/byte budgets are still caller responsibilities.
Evidence: `/tmp/gunz-utils-offline-rounds6-9-oracles.json` and
`/tmp/gunz-utils-offline-rounds6-9-global-state.json`.

## Final executed local checks
- Full Python 3.11 and 3.12: **1742 passed, 38 justified skips** each.
- Each forced fallback native packet: **60 passed, 31 native-only skips**.
- Each actual compiled native packet: **91 passed**, no skips.
- Ruff/mypy/private local style: pass; zero style violations, 101 advisory warnings.
- Strict final Sphinx build: pass using `confoverrides={'intersphinx_mapping': {}}`.
- Wheel and sdist build: local `python -m build --no-isolation`.
- Fresh wheel and sdist-derived wheel core environments: installed origin,
  py.typed and zero-dependency import checks pass. Installed wheel also exercises
  repaired Result/deep traversal behavior.
- Optional validation/project/observability/secure/plot checks: pass after offline
  installation of the final wheel into existing cached-dependency environments.
  The plot case performs an actual headless Agg render.
- Release metadata: pass with existing untagged-version/next-patch advisories.

The 38 ordinary skips are 31 native cases exercised separately plus seven real
Windows/macOS cases requiring those hosts. The normal benchmark deprecation
warning remains. New regressions were not weakened or marked xfail.

This is an offline verification variant, not a claim that the unmodified canonical
aggregate/fresh dependency-download matrix ran. Cached extras are explicitly
separate from fresh minimal artifact environments. Native Windows/macOS,
independent review before main merge, arbitrary hostile hook confinement and
whole-package memory-leak certification remain outside this executed scope.

Final source/test/configuration/fragment fingerprint (306 files): `b912b51a45747a6325e2cf930e27948696360e989c0ce9cb8cabc664c59d91fb`.
Actual exit-code summary: `/tmp/gunz-utils-offline-rounds6-9-final-summary.json`.
Logs: `/tmp/gunz-utils-offline-rounds6-9-final311.log`, `final312.log`,
`final-lint.log`, `final-docs.log` and `final-packaging.log` under the same prefix.
