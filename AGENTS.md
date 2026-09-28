# AGENTS.md — gunz-utils

This file is the agent-facing operating policy for work in this repository.
It is repository-specific and tool-neutral.

## 1. Sources of truth and precedence

Use the repository itself as the source of truth. When documents disagree,
prefer executable configuration and current code over historical notes.

Canonical sources:

1. `pyproject.toml` — package metadata, Python floor, extras, Ruff, pytest, mypy.
2. `.github/workflows/ci.yml`, `scripts/audit_ci.py`, and `scripts/ci.py` — hosted/local CI behavior.
3. `scripts/release.py`, `changes/README.md`, and
   `docs/development/releases.md` — versioning and releases.
4. `SECURITY.md` — vulnerability reporting and disclosure.
5. `docs/design/package-api-policy.md` — public API and dependency boundaries.
6. `CONTRIBUTING.md` — contributor workflow.
7. Maintained documentation under `docs/source/`, `docs/development/`,
   `docs/design/`, and `docs/guides/`.

Files under `docs/tasks/done/` are historical records. They may describe
obsolete tools, paths, commands, CI layouts, or policies and are not current
instructions.

There is no maintained top-level `guides/` directory. Do not recreate it.
Reusable documentation belongs under `docs/`.

## 2. Package invariants

Preserve these unless a deliberate, reviewed breaking change says otherwise:

- Python support starts at 3.11.
- The core package has no mandatory runtime dependencies.
- Third-party integrations remain optional extras.
- `src/gunz_utils/py.typed` must ship in built wheels.
- Stable subsystem APIs are namespace-first; do not bulk-export new APIs from
  `gunz_utils` root without an explicit compatibility reason.
- Modules with public `__all__` contracts must remain represented in the API
  reference and contract tests.
- Optional third-party packages must not leak into core import-time behavior.
- Reference implementations remain pure Python; acceleration is optional and
  must preserve observable semantics.

Before adding a dependency or root-level export, check
`docs/design/package-api-policy.md`.

## 3. Change workflow

For non-trivial work:

1. Start from current `main`.
2. Use a focused branch.
3. Inspect the relevant implementation, tests, configuration, and maintained
   documentation before editing.
4. Reuse existing primitives instead of adding overlapping helpers.
5. Keep code, tests, docs, and release metadata consistent in the same change.
6. Add a changelog fragment for user-visible changes.
7. Run focused checks while iterating.
8. Run the canonical full local gate before merge when the environment permits.

Do not mix unrelated refactoring into a bug fix or feature unless required for
correctness.

## 4. CI policy

Hosted CI is intentionally local-first and credit-conscious.

GitHub Actions runs only for:

- pushes to `main`;
- pull requests whose base branch is `main`.

Feature-branch pushes must not enable or add hosted CI runs merely for
convenience.

The single hosted job is `CI / verify`. Its fail-fast order is:

1. release/version/changelog metadata;
2. Ruff;
3. mypy;
4. full Python 3.11 pytest suite;
5. strict Sphinx documentation;
6. packaging and optional-dependency isolation;
7. full Python 3.12 compatibility pytest suite.

Canonical local gate:

```bash
./scripts/verify.sh
```

Aggregate dispatcher:

```bash
python scripts/audit_ci.py --summary-json tmp/ci-summary.json
```

`scripts/ci.py all` remains a focused fail-fast helper; the aggregate
dispatcher is the preferred pre-merge verification path.

Useful focused gates:

```bash
python scripts/release.py check
python scripts/ci.py lint
python scripts/ci.py test
python scripts/ci.py docs
python scripts/ci.py packaging
```

Do not add parallel or duplicate workflows for checks already represented by
`scripts/audit_ci.py` / `scripts/ci.py` unless a distinct permission or security
boundary requires it.
Keep hosted workflow permissions minimal and preserve cancellation and timeout
behavior.

Ruff formatting is configured but is not a repository gate. Ruff linting is.

## 5. Versioning and release management

`pyproject.toml [project].version` is the only static package-version source.

Runtime version rules:

- `gunz_utils._version` resolves installed package metadata.
- `gunz_utils.__version__` uses the shared resolver.
- Historical module-level `__version__` compatibility aliases may remain.
- Do not add independent static version literals to modules.
- Sphinx derives its release value from installed package metadata.

Ordinary development must not edit the top of `CHANGELOG.md`. Add one fragment:

```text
changes/<unique-id>.<category>.md
```

Supported categories and minimum SemVer impact are defined in
`changes/README.md`:

- `breaking`, `removed` -> major;
- `added`, `changed`, `deprecated` -> minor;
- `security`, `fixed`, `performance`, `docs`, `internal` -> patch.

Release commands:

```bash
python scripts/release.py check
python scripts/release.py status
python scripts/release.py prepare X.Y.Z
python scripts/release.py verify
```

Release invariants:

- release commit message is exactly `chore(release): vX.Y.Z`;
- package metadata and changelog heading match `X.Y.Z`;
- tag `vX.Y.Z` is created only after the release commit is on `main` and
  verified;
- the GitHub Release must refer to that exact tag;
- do not invent retroactive tags just to fill historical gaps.

See `docs/development/release-history.md` before changing historical release
metadata.

## 6. Security rules and audit checklist

Security-sensitive work requires explicit threat-oriented review, not only
functional tests.

Never:

- commit credentials, tokens, private keys, secret-bearing fixtures, or
  production data;
- disclose an undisclosed vulnerability in a public issue, PR, changelog
  fragment, or test fixture;
- use `assert` as production runtime validation;
- interpolate untrusted values into shell command strings when structured
  subprocess arguments can be used;
- add custom cryptography when established primitives already exist.

Use explicit exceptions and boundary validation in production code.

When a change touches a security boundary, audit the relevant items below.

### Filesystem and paths

- path traversal and rooted-path containment;
- symlink redirection and TOCTOU behavior;
- atomic publication and failure cleanup;
- permissions applied before publication where confidentiality matters;
- reserved names and platform-specific path behavior.

Prefer existing helpers such as `safe_path_join`, `open_path_under_base`,
atomic writes, content-store integrity checks, and shell-free sync primitives.

### Subprocess and command execution

- no unintended `shell=True` behavior;
- argument boundaries preserved as sequences;
- output and resource bounds where untrusted programs or inputs are possible;
- cancellation and process-exit signals are not converted into ordinary values.

### Secrets and diagnostics

- redact secrets before logging or serializing diagnostics;
- avoid retaining arbitrary exception text in persisted reports when it may
  contain secrets;
- do not expose encryption keys or passphrases through defaults, logs, or
  provenance.

### Network and external input

- validate URI authorities, hosts, and delimiters;
- bound retries, delays, timeouts, payload sizes, item counts, and nesting depth;
- treat provider values such as retry delays as untrusted input;
- preserve IDNA/IPv6 handling and injection protections.

### Serialization, storage, and provenance

- deterministic serialization must not weaken validation;
- content-addressed storage must verify integrity and reject unsafe path or
  symlink behavior;
- provenance metadata must be allowlisted and avoid secret-bearing environment
  capture;
- reject cyclic or unbounded input graphs where relevant.

### Concurrency and async code

- preserve cancellation semantics;
- bound concurrency and queues;
- prevent stale ownership or lease work from continuing after ownership loss;
- test races around locks, markers, retries, and publication.

Security fixes require focused regression tests and an appropriate
`security` or `fixed` changelog fragment.

For vulnerability reporting and disclosure, follow `SECURITY.md`.

## 7. Testing and correctness

The complete test suite uses pytest:

```bash
python -m pytest
```

Static checks:

```bash
python -m ruff check src tests benchmarks scripts
python -m mypy src/gunz_utils
```

Algorithmic changes must follow
`docs/guides/algorithm-correctness-audit.md`, the design protocol under
`docs/design/audit/`, and update
`docs/audits/algorithm-registry.md` when they add, change, repair, or retire
an algorithmic contract. Explicitly cover parameter domains, numerical
finiteness and bounds where applicable, invariants, independent oracles,
special cases, complexity/boundedness, and failure atomicity. Do not promote an
audit entry to A3 or A4 until the required focused/full verification has
actually executed successfully.

Do not weaken a test merely to make a gate green. Fix the implementation or the
test's incorrect assumption and preserve a regression test for the discovered
failure.

When changing compatibility-sensitive behavior, test both the canonical API and
supported historical aliases.

When changing package boundaries or extras, run `python scripts/ci.py packaging`.
That gate verifies zero-dependency imports, optional extras in isolated venvs,
wheel and sdist installation, source-shadowing protection, plotting isolation,
and the PEP 561 marker.

## 8. Documentation and public API

Maintained docs belong under `docs/`; do not create a root `guides/`
directory.

- README: concise scope, installation, major capabilities, navigation.
- `docs/source/`: user and API documentation.
- `docs/development/`: maintainer and release process.
- `docs/design/`: architecture and durable design decisions.
- `docs/guides/`: maintained operational guides such as CI rationale.
- `docs/tasks/`: task records; archived records are not policy.

Strict docs build:

```bash
python scripts/ci.py docs
```

Sphinx warnings are errors. If API coverage exposes a malformed existing
docstring, repair the docstring or parser configuration rather than hiding the
public namespace.

Public namespaces with `__all__` are expected to remain covered by
`docs/source/api.rst` and repository contract tests.

## 9. Repository hygiene

Do not commit local, editor, agent, deployment, or generated caches, including:

- `.gemini/`;
- `.jules/`;
- `.wrangler/`;
- Python, Ruff, mypy, and pytest caches;
- generated Sphinx output under `docs/_build/`;
- transient files under `tmp/`.

Do not add tool-specific operating protocols that override repository policy.
Agent tooling may consume this file, but the rules must remain usable by any
developer or automation.

Keep historical task records intact unless they contain sensitive information
or the user explicitly requests deletion. Prefer indexing and clarifying history
over erasing provenance.

## 10. Definition of done

A change is ready only when applicable items are satisfied:

- implementation is focused and typed;
- relevant tests are added or updated;
- Ruff and mypy pass;
- pytest passes;
- strict docs pass when docs or public API changed;
- packaging isolation passes when metadata, dependencies, or build behavior
  changed;
- security audit performed for security-sensitive changes;
- changelog fragment added for user-visible changes;
- version and release invariants remain valid;
- no generated or tool-specific artifacts were introduced.
