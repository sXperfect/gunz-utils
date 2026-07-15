# AGENTS.md — `gunz-utils`

> Source of Truth for AI agents and developers working in this repository.
> Authoritative on stack, environment, conventions, and governance.
> Supersedes any conflicting instructions from generic agent defaults.

---

## 1. Project Identity

| Field | Value |
|:------|:------|
| **Name** | `gunz-utils` |
| **Version** | `1.2.0` (see `pyproject.toml`) |
| **Description** | General-purpose Python utilities for the Gunz ecosystem. Enhanced Enums, security primitives, UpstreamClient protocol, Fernet secret store. |
| **License** | BSD 3-Clause (`LICENSE.md`) |
| **Repository** | https://github.com/sXperfect/gunz-utils |
| **Issue Tracker** | https://github.com/sXperfect/gunz-utils/issues |
| **Primary Author** | Yeremia Gunawan Adhisantoso `<adhisant@tnt.uni-hannover.de>` |
| **Commit Author** | Author identity from `pyproject.toml` unless overridden locally via `git config user.{name,email}`. |

---

## 2. Technical Stack

### 2.1 Language & Runtime
- **Python ≥ 3.11** (strict floor; do not target lower).
- Type hints are mandatory on all public APIs.
- `from __future__ import annotations` is used at the top of modules.

### 2.2 Core Dependencies (production)
| Package | Min Version | Purpose |
|:--------|:-----------:|:--------|
| `pydantic` | `>=2.0.0` | Data models, validation |
| `cryptography` | `>=42.0.0` | Fernet encryption, secure primitives |
| `gitpython` | `>=3.1.0` | Repository metadata |

### 2.3 Build System
- **Backend:** `hatchling` (PEP 517).
- **Wheel target:** `src/gunz_utils` (src-layout, strict).
- **Sdist target:** `src/`.

### 2.4 Optional Dependencies
- `docs` extra: `sphinx`, `furo`, `myst-parser`, `sphinx-autodoc-typehints`.

### 2.5 Testing Toolchain
- **Framework:** `pytest` (configured via `pyproject.toml`/defaults).
- **Coverage:** `pytest-cov` recommended but not yet declared; install locally if used.
- **Test location:** `tests/test_*.py` mirroring the public API surface.

### 2.6 Linting / Formatting
- **Ruff** is active (presence of `.ruff_cache/` confirms use).
- Configuration: `pyproject.toml` `[tool.ruff]` section (to be added if missing — see `TASKS.md`).
- Run `ruff check .` and `ruff format --check .` before commits.

### 2.7 Documentation
- **Sphinx + Furo** theme, MyST parser.
- Source: `docs/source/`.
- Build script: `docs/build_docs.sh`.

---

## 3. Environment Isolation (mamba)

> **Rule:** All Python commands MUST run inside the project's mamba environment.
> Never install packages globally. Never invoke `pip install` against the system interpreter.

### 3.1 Environment Specification

| Field | Value |
|:------|:------|
| **Manager** | `mamba` (preferred) / `conda` (fallback) |
| **Environment name** | `gunz-utils` |
| **Python version** | `3.11` |
| **Activation** | `mamba activate gunz-utils` |

### 3.2 One-Time Bootstrap

```bash
# 1. Create the environment from the spec (first time only)
mamba create -n gunz-utils python=3.11 -y

# 2. Activate
mamba activate gunz-utils

# 3. Install in editable mode with docs extras
pip install -e ".[docs]"

# 4. Install dev tooling
pip install pytest ruff mypy
```

### 3.3 Daily Workflow

```bash
mamba activate gunz-utils
pytest                     # run all tests
ruff check .               # lint
ruff format .              # format
mypy src/gunz_utils        # static type check
```

### 3.4 Constraint
- Do not run `pip install <pkg>` outside an activated mamba env.
- Do not introduce `venv`, `virtualenv`, `uv`, or `poetry` as the primary manager — mamba is canonical.
- The CI pipeline (`.github/workflows/`) must use the same Python version (3.11).

---

## 4. Directory Structure (per Protocol §7)

```
gunz-utils/
├── AGENTS.md                 # THIS FILE — Source of Truth
├── README.md
├── LICENSE.md
├── pyproject.toml
├── .gitignore                # Includes .hyperhedron/
│
├── src/
│   └── gunz_utils/           # Production package (src-layout)
│       ├── __init__.py       # PEP 562 lazy import shim
│       ├── enums.py
│       ├── security.py
│       ├── crypto.py
│       ├── secure_store.py
│       ├── validation.py
│       ├── models.py
│       ├── project.py
│       ├── logging.py
│       └── upstream_protocol.py
│
├── tests/                    # Verification suite
│   ├── test_enums.py
│   ├── test_enums_security.py
│   ├── test_security.py
│   ├── test_security_reserved.py
│   ├── test_validation.py
│   ├── test_validation_leak.py
│   ├── test_secure_store.py
│   └── test_project.py
│
├── docs/                     # Documentation Hub
│   ├── TASKS.md              # Active + Pending task index
│   ├── TASKS_ARCHIVE.md      # Done/Archived task log
│   ├── design/
│   │   ├── specs/            # SRS documents (linked to definitions)
│   │   ├── definitions/      # Component YAML definitions
│   │   ├── adr/              # Architecture Decision Records
│   │   └── assets/           # Images, diagrams, UI/UX assets
│   ├── analysis/             # Reports, post-mortems
│   ├── tasks/
│   │   ├── pending/          # Approved, not yet started
│   │   ├── active/           # Currently implementing
│   │   └── done/             # Completed (historical archive)
│   ├── source/               # Sphinx source
│   ├── _build/               # Sphinx output (gitignored)
│   └── templates/            # Task file templates
│
├── scripts/                  # Automation & utilities
│   ├── shell/                # DevOps / runner scripts
│   └── tests/                # Ad-hoc diagnostic scripts
│
├── configs/                  # Configuration files (YAML/JSON/TOML)
│
├── benchmarks/               # Performance benchmarks (existing)
├── guides/                   # Project-local guides (existing)
│
├── tmp/                      # Transient data (gitignored)
│   ├── logs/
│   └── db/
│
└── .hyperhedron/             # External knowledge base (gitignored, symlink farm)
    ├── guides/               # Shared SOPs
    ├── deep_research/        # Technical research papers
    ├── protocols/            # Versioned procedural standards
    └── memory/               # Project-specific agent memory
        ├── INDEX.md
        ├── PROTOCOL.md
        ├── sessions/         # Per-session logs
        └── lessons/          # Lessons learned
```

### 4.1 Namespace Isolation
- All production code lives under `src/gunz_utils/`.
- All tests live under `tests/`.
- Do not create top-level modules outside `src/gunz_utils/`.

### 4.2 Reuse Mandate
- Before writing a utility, search `.hyperhedron/guides/` for shared SOPs and `src/gunz_utils/` for existing helpers.
- Prefer extending existing utilities over forking.

---

## 5. Git & Commit Standards

### 5.1 Conventional Commits
All commit messages MUST follow the [Conventional Commits](https://www.conventionalcommits.org/) spec:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Allowed types:** `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`.

**Examples (from repo history):**
```
fix(security): prevent bypass of reserved filename check
perf: optimize windows reserved filename check in sanitize_filename
feat: add input length validation to Enum fuzzy matching
```

### 5.2 Author Identity
- Primary identity (from `pyproject.toml`): Yeremia Gunawan Adhisantoso `<adhisant@tnt.uni-hannover.de>`.
- Override locally only if the developer has their own git identity (`git config user.{name,email}`).
- Never commit as a generic identity (e.g., `root`, `opencode`).

### 5.3 Commit Hygiene
- One logical change per commit.
- Tests MUST be included with `feat` and `fix` commits.
- Never commit secrets, large binaries, or `.env` files.
- Do not commit unless the user explicitly requests it.

### 5.4 Branch Hygiene
- `main` is the protected release branch.
- Feature branches: `feat/<short-kebab-description>`.
- Fix branches: `fix/<short-kebab-description>`.

---

## 6. Documentation Standards

### 6.1 Doxygen / NumPy Docstrings
All **public APIs** MUST include a docstring following the NumPy-style format (preferred by this project) or Google-style. The docstring must explain:
- **What** the function does (one-line summary).
- **Why** it exists (architectural intent, not just mechanics).
- **Parameters** with types and constraints.
- **Returns** with type and semantics.
- **Raises** if applicable.
- **Examples** for non-trivial APIs.

Example:
```python
def safe_path_join(base: Path, *parts: str) -> Path:
    """Join paths while preventing traversal outside `base`.

    Resolves `..` and absolute path components. Raises if the result
    escapes `base`. Used by the secure store to confine writes to a
    per-user directory.

    Parameters
    ----------
    base : Path
        Confined root directory.
    *parts : str
        Path components to append.

    Returns
    -------
    Path
        The resolved, contained path.

    Raises
    ------
    ValueError
        If the resolved path is outside `base`.
    """
```

### 6.2 Specifications & Design Linkage
- **Definitions** (structure) live in `docs/design/definitions/*.yaml`.
- **Specs** (behavior) live in `docs/design/specs/*.md`.
- Every SRS document MUST reference its definition via metadata header:

```markdown
---
title: "SRS: SecureStore"
definition: docs/design/definitions/secure_store.yaml
version: 1.0
status: active
---
```

### 6.3 Documentation Versioning
- Guides and research documents use `X.Y` format (no patch).
- Protocol documents use `X.Y.Z` with `CHANGELOG.md`.

---

## 7. Task Management

### 7.1 Master Indices
- `docs/TASKS.md` — Active + Pending tasks ONLY. Living document.
- `docs/TASKS_ARCHIVE.md` — Done/Archived tasks. Historical record.

### 7.2 Task Files
- Location: `docs/tasks/{pending,active,done}/YYYY.MM.DD-<component_slug>-<task_title_with_underscore>.md`.
- The `<component_slug>` must match the relevant subdirectory in `src/gunz_utils/` or `scripts/`.
- Physical files MUST move between `pending/`, `active/`, and `done/` as status changes.

### 7.3 Role-Based Templates
Agents MUST initialize new task files using the template matching the assigned role from `docs/templates/`:
- **Programmer**: `TASK_PROGRAMMER.md` — implementation, refactor, bug fix.
- **Researcher**: `TASK_RESEARCHER.md` — experiment, benchmark, analysis.
- **General/Ops**: `TASK_GENERAL.md` — maintenance, coordination.

### 7.4 Task Table Format
```markdown
| Task ID | Date | Description | Status |
|:---:|:---:|:---|:---:|
| [task-slug](tasks/done/YYYY-MM-DD-slug.md) | YYYY-MM-DD | Short description | Done |
```

---

## 8. Memory System Integration

### 8.1 Location
The project's agent memory lives under `.hyperhedron/memory/` (which symlinks to `hyperhedron-memory/memory/gunz-utils/`).

### 8.2 Structure
- `INDEX.md` — Master index of memory entries.
- `PROTOCOL.md` — Memory conventions.
- `sessions/` — Per-session logs.
- `lessons/` — Lessons learned (high-signal, durable).

### 8.3 Usage
- **Before starting work:** consult `INDEX.md` and `.hyperhedron/guides/` for relevant SOPs.
- **After completing work:** append a brief session entry if the work yielded reusable insights.
- **Never** write memory files outside `.hyperhedron/memory/`.

### 8.4 Namespace Rule
`.hyperhedron/memory/` is the symlink — write files inside it directly; the symlink handles routing.

---

## 9. Agent Operational Rules (Mandatory)

### 9.1 Universal Safety
| Rule | Mandate |
|:-----|:--------|
| Anti-looping | Max 3 failed attempts at the same fix; then stop and ask. |
| Transactional | No "patching the patch"; propose rollback instead. |
| Data integrity | Request checkpoint before bulk edits (>3 files) or deletions. |
| Context hygiene | Suppress verbose output with `2>&1 \| tail`, `grep -C`, etc. |

### 9.2 Context Economy
- Always run `wc -l <file>` before reading; apply the Reading Decision Tree.
- For logs: `grep -nC 5 "error\|warn\|fail\|traceback" <file> | head -n 40`.
- For source >1000 lines: section-based navigation via `grep -n "def \|class " <file>`.

### 9.3 Delegation Pattern
- Decompose work into atomic units before starting.
- Delegate each unit to specialized agents (not direct implementation).
- Always verify delegated results (lsp_diagnostics, tests, manual smoke).

### 9.4 Hard Blocks
- ❌ Never use `as any`, `# type: ignore`, or `@ts-expect-error` equivalents.
- ❌ Never commit without explicit user request.
- ❌ Never install packages globally — always in the mamba env.
- ❌ Never delete legacy code without explicit user direction.
- ❌ Never introduce new dependencies without explicit permission.

---

## 10. CI / CD

- **CI Provider:** GitHub Actions (see `.github/workflows/`).
- **Python matrix:** `3.11`.
- **Triggers:** push to `main`, pull requests.
- **Status badge:** see `README.md`.

---

## 11. Pointers

| Topic | Location |
|:------|:---------|
| Architecture overview | `docs/design/` (when populated) |
| Public API surface | `src/gunz_utils/__init__.py` |
| Test patterns | `tests/` |
| Past decisions | `git log` + `.hyperhedron/memory/sessions/` |
| Shared SOPs | `.hyperhedron/guides/` |
| Protocol standards | `.hyperhedron/protocols/` |
| Sphinx docs | `docs/source/` |

---

## 12. Maintenance Log

| Date | Change | Author |
|:----:|:-------|:-------|
| 2026-07-15 | Initial `AGENTS.md` created during workspace initialization. mamba chosen as env manager. `.jules/` legacy configs removed. | OpenCode (Sisyphus) |