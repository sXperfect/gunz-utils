# Testing Taxonomy & Architecture Guide

This guide describes the unit and integration testing structure for `gunz-utils`,
providing contributors and agents with standard conventions for categorizing,
marking, and locating tests.

## 1. Core Principles

1. **Isolation-First:** Tests for the core package must not require or import
   optional third-party dependencies (`pydantic`, `cryptography`, `gitpython`, `loguru`, `matplotlib`).
2. **Deterministic Execution:** No test should depend on external network access,
   ambient machine state, or unseeded random generators.
3. **Cheapest-First Local Feedback:** Fast in-memory unit tests should run in <2 seconds.
   Heavy stress, subprocess, or multi-process tests must be tagged with `@pytest.mark.slow`.
4. **Mirroring Source Structure:** New unit tests should be placed in paths corresponding
   to their source module under `tests/` rather than creating historical sprint-named files.

## 2. Directory Layout & Boundaries

```text
tests/
├── conftest.py                   # Global fixtures and test configuration
├── test_core/                    # Core library tests (dependency-free)
│   ├── test_*_<module>.py        # Unit tests corresponding to src/gunz_utils/<module>.py
│   ├── test_repository_*.py      # Static contract tests for package & policy
│   ├── test_ci_policy.py         # Static contract tests for CI workflow rules
│   └── test_release_tooling.py   # Unit tests for scripts/release.py
├── test_ext_stdlib/              # Stdlib fallback tests without optional dependencies
├── test_validation/              # Pydantic backend tests (requires .[validation])
├── test_project/                 # GitPython backend tests (requires .[project])
├── test_observability/           # Loguru backend tests (requires .[observability])
└── test_secure/                  # Cryptography backend tests (requires .[secure])
```

## 3. Standard Pytest Markers

The repository configures `--strict-markers` in `pyproject.toml`. The supported
markers are:

| Marker | Description | Typical Use Cases |
|:---|:---|:---|
| `@pytest.mark.slow` | Long-running test (>0.5s) | Subprocess timeouts, concurrency stress loops, invariant stress tests. |
| `@pytest.mark.integration` | Multi-subsystem integration | Workflow DAG execution, content-store + provenance graph cascades. |
| `@pytest.mark.policy` | Governance & contract checks | `test_ci_policy.py`, `test_repository_contracts.py`. |
| `@pytest.mark.isolation` | Environment isolation | Packaging venv matrix tests, clean environment checks. |

### Running Filtered Test Suites

```bash
# Run fast unit tests only (skipping slow tests)
python -m pytest -m "not slow"

# Run policy & contract tests only
python -m pytest -m "policy"

# Run a focused module test
python -m pytest tests/test_core/test_retry.py -v
```

## 4. Writing New Tests

- Use pure `pytest` functions or `unittest.TestCase` where appropriate.
- Prefer `tmp_path` fixture for temporary filesystem operations.
- Avoid asserting on non-deterministic error strings that could leak environment secrets.
- In security or retry tests, prefer explicit bounds over indefinite loops.
