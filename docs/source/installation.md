# Installation

**Gunz Utils** is a Python 3.11+ utility library with a dependency-free core.
Third-party integrations are available only through optional extras.

## Install directly from GitHub

Core only:

```bash
python -m pip install "gunz-utils @ git+https://github.com/sXperfect/gunz-utils.git"
```

With the common runtime integrations:

```bash
python -m pip install "gunz-utils[all] @ git+https://github.com/sXperfect/gunz-utils.git"
```

Add plotting when benchmark visualization is needed:

```bash
python -m pip install "gunz-utils[all,plot] @ git+https://github.com/sXperfect/gunz-utils.git"
```

For reproducible deployments, pin the VCS URL to a reviewed tag or commit SHA
instead of tracking the repository head.

## Install from a local checkout

```bash
git clone https://github.com/sXperfect/gunz-utils.git
cd gunz-utils
python -m pip install -e .
```

For local development:

```bash
python -m pip install -e ".[all,plot,docs]"
python -m pip install pytest==9.0.3 ruff==0.14.10 mypy==1.19.1
```

The explicit developer-tool versions above mirror the hosted CI workflow.

## Dependencies

The core distribution has no runtime dependencies:

```toml
dependencies = []
```

Importing `gunz_utils` therefore does not require Pydantic, Cryptography,
GitPython, Loguru, or Matplotlib.

Optional extras are defined in `pyproject.toml`:

| Extra | Adds | Representative functionality |
|---|---|---|
| `validation` | `pydantic>=2.4.0` | Pydantic-backed runtime validation |
| `project` | `gitpython>=3.1.62` | Git-aware project-root discovery |
| `observability` | `loguru>=0.7.0` | Structured logging setup |
| `secure` | `cryptography>=50.0.1` | Encryption and secure storage |
| `plot` | `matplotlib>=3.10.9` | Benchmark plotting |
| `all` | validation + project + observability + secure | Common runtime integrations |
| `docs` | Sphinx toolchain | Local documentation builds |

`all` intentionally does not include `plot` or `docs`.

## Optional integration behavior

Common optional symbols are exposed lazily from the package root:

```python
from gunz_utils import SecureStore, resolve_project_root, setup_logging, type_checked
```

Install the matching extra before using a symbol whose backend depends on a
third-party package.

Where provided, stdlib alternatives live under `gunz_utils.ext.*`. The API
reference documents which backend each symbol uses.
