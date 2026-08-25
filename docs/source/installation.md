# Installation

**Gunz-Utils** is the foundational core of the Gunz ecosystem, providing shared enums, validation logic, project management, observability, and security utilities.

## Standard Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/sXperfect/gunz-utils.git
```

## Development Environment

```bash
# Create the environment
mamba create -n gunz-utils python=3.11

# Activate it
mamba activate gunz-utils

# Install in editable mode
pip install -e .
```

## Dependencies

Gunz-Utils' core install pulls the following runtime dependencies:

| Package | Version | Why |
|---|---|---|
| `pydantic` | `>=2.0.0` | `BaseModel` support in `models.py`; `validate_call` in `ext.validation_pydantic` |
| `cryptography` | `>=42.0.0` | `Fernet` + `AESGCM` + `PBKDF2` in `ext.secure_crypto` and `ext.secure_store` |
| `gitpython` | `>=3.1.0` | `Repo` for project-root detection in `ext.project_gitpython` |
| `loguru` | `>=0.7.0` | Structured logging in `ext.observability_loguru`; debug logging in `ext.project_gitpython` |

## Optional Dependencies

To minimize install footprint for projects that don't need the heavy modules,
install narrower subsets of gunz-utils via extras:

| Extra | Pulls in | Unlocks |
|---|---|---|
| `validation` | `pydantic>=2.0.0` | `type_checked` decorator (default backend) |
| `project` | `gitpython>=3.1.0`, `loguru>=0.7.0` | `resolve_project_root` (default backend) |
| `observability` | `loguru>=0.7.0` | `setup_logging` (default backend) |
| `secure` | `cryptography>=42.0.0` | `SecureStore`, `encrypt`, `decrypt` |
| `all` | everything in `dependencies=` | every default backend |
| `docs` | sphinx, myst-parser, sphinx-autodoc-typehints, sphinx_rtd_theme | building the documentation locally |

Examples:

```bash
pip install gunz-utils[validation]    # add pydantic explicitly
pip install gunz-utils[secure]       # add cryptography
pip install gunz-utils[all]           # everything
pip install gunz-utils[all,docs]      # everything + docs tooling
```

Stdlib-only fallback paths are also available without any of the
above extras — see the *Optional Dependencies* section in
`concepts.md` for details on `gunz_utils.ext.*` modules.