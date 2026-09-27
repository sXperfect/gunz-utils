# CI Lessons Learned

This record captures concrete issues found while validating the CI/release
refactor through pull request #55. Keep these as regression lessons rather than
one-off debugging notes.

## 1. Test the real pull-request path

Static inspection of workflow YAML is not enough. Pull-request workflows check
out GitHub's synthetic merge commit, not necessarily the feature-branch HEAD.

The pre-merge validation therefore used a real PR targeting `main` before
merge. That exercised the exact checkout, event payload, permissions, tag
availability, caches, and merge-state behavior that the final workflow uses.

Lesson: before merging CI changes, validate at least one real PR-triggered run.

## 2. Put cheap checks first

The first PR run failed at Ruff because of one `UP037` annotation rule in
`scripts/release.py`.

Because Ruff ran before mypy, pytest, documentation, packaging isolation, and
Python 3.12 compatibility, the workflow stopped immediately and avoided most
expensive work.

Lesson: order checks by cost and expected failure frequency, not by conceptual
importance.

## 3. Repository tooling must lint itself

Adding `scripts/` to Ruff coverage exposed the release-tool annotation defect
that would have escaped the previous `src tests benchmarks` lint scope.

Lesson: CI/release helper code is production engineering infrastructure and must
be linted and tested with the library.

## 4. Avoid namespace collisions in Sphinx configuration

The second PR run passed release metadata, Ruff, mypy, and the full Python 3.11
test suite but failed strict Sphinx validation.

The cause was:

```python
from importlib.metadata import version
```

inside `docs/source/conf.py`. Sphinx reserves the configuration variable
`version`; importing a function under that name caused Sphinx to interpret the
function object as its version string. Strict mode reported an invalid config
type and later failed while generating the object inventory.

The fix is to alias the import:

```python
from importlib.metadata import version as package_version
```

Lesson: Sphinx `conf.py` is a configuration namespace. Imported symbols can
silently become configuration variables, so generic names such as `version`,
`release`, `project`, `extensions`, and `language` require special care.

## 5. Strict documentation builds are valuable

Without `-W`, the Sphinx warning could have been overlooked even though the
configuration was semantically broken.

Lesson: documentation warnings should remain fatal in CI for a reusable library.

## 6. Preserve full Git history when release checks inspect tags

The release metadata checker compares the current version to Git tags.
The workflow therefore uses:

```yaml
fetch-depth: 0
```

A shallow checkout would make tag/history validation unreliable.

Lesson: when repository checks depend on history or tags, checkout depth is part
of the validation contract.

## 7. Historical inconsistency should not be repaired by fabrication

The audit found tags through `v1.8.0`, while `1.9.0` and `1.10.0` exist in
source/history without matching release tags.

The new release checker reports this as a warning and documents the history
rather than creating retrospective tags.

Lesson: release automation should make future state consistent, not rewrite
uncertain historical state.

## 8. One runner is appropriate for this repository

The old layout created separate jobs for tests, compatibility, linting,
packaging, documentation, and aggregation. Most jobs lasted well under two
minutes and repeated environment setup.

The new sequential workflow trades some wall-clock parallelism for substantially
less duplicated setup and a simpler required-check model.

Lesson: small repositories with short gates should optimize for runner
efficiency and deterministic sequencing before optimizing for maximum parallelism.

## 9. Keep feature-branch CI disabled

A temporary feature-branch trigger was considered for validation, but the final
policy uses the intended PR-to-main event instead. The workflow file was restored
to main-only push plus PR-to-main before normal validation continued.

Lesson: testing CI should exercise the final trigger path whenever possible,
rather than leaving temporary trigger exceptions behind.

## 10. Treat CI design as repository documentation

The workflow YAML alone does not explain why sequential execution, trigger
restrictions, release checks, history depth, caching, or strict docs exist.

Lesson: maintain both the executable workflow and the design rationale under
`docs/guides/ci/` so future refactors preserve the constraints intentionally.
