# Best Practices for Python Application Development
_version: 5.2.0_

**Unless stated explicitly in the code, follow this best practice guide when writing, updating, and
improving the code.**

This document outlines a set of best practices and general requirements for developing robust,
usable, and maintainable applications in Python. The principles cover general code quality, project
structure, and specific guidance for command-line interfaces (CLIs), object-oriented design, and
data structures, with a focus on leveraging Python 3.11's features for high performance.

## General Project & Code Quality
---

These principles apply to any Python project, regardless of its primary interface.

### Dependency & Environment Management

A project should be reproducible and easy for others to set up.

- **Virtual Environments**: Always develop within a Python virtual environment (e.g., `venv`) to
  isolate project dependencies and avoid conflicts.
- **Declare Dependencies**: List all required third-party libraries in a `requirements.txt` file or,
  for more complex projects, a `pyproject.toml`.
- **Mandate Python 3.11**: The project **must** target and require **Python 3.11** as the minimum
  version. This must be enforced in the project's configuration (e.g., in `pyproject.toml`) and
  stated clearly in the `README.md`.

### Code Formatting & Linting

Consistent, clean code is easier to read, debug, and maintain. To that end, we favor clarity and
simplicity over unnecessarily clever or complex code.

- **Code Formatting**: Use an automated code formatter like `Black` to enforce a consistent,
  objective style across the entire codebase.
- **Linting**: Use a linter like `Ruff` or `Flake8` to automatically catch common errors, style
  issues, and potential bugs before they become problems.
- **One Statement Per Line**: Avoid multiple statements or assignments on a single line.

    **Don't do this:**
    ```python
    x = 5; y = 10
    mu, var = outputs["mu"], outputs["var"]
    ```

    **Do this instead:**
    ```python
    x = 5
    y = 10
    mu = outputs["mu"]
    var = outputs["var"]
    ```

- **One Argument Per Line**: For function definitions and class initializers (`__init__`), list one
  argument per line. This rule should be followed strictly to ensure maximum readability and
  consistency, even when arguments seem simple or related. The opening parenthesis should be
  followed by a newline, and the closing parenthesis should be on its own line, indented to the same
  level as the line containing the opening parenthesis.
- **Group Related Arguments**: Use comments to group function arguments by their purpose or context,
  especially in functions with many parameters.

    ```python
    import pathlib
    import torch

    def train_model(
        #? --- Data Configuration ---
        dataset_path: str | pathlib.Path,
        batch_size: int,
        num_workers: int,
        #? --- Model Hyperparameters ---
        model_name: str,
        learning_rate: float,
        dropout_rate: float | None = 0.0,
        #? --- Training & Checkpointing ---
        device: torch.device,
        num_epochs: int,
        checkpoint_dir: str | pathlib.Path,
    ):
        """Trains a model with specified data and hyperparameters."""
        # ...
    ```

### Import Conventions

Clean imports make code easier to understand and maintain.

- **Grouping and Ordering**: Imports should be at the top of the file, grouped in the following
  order:
    1.  Standard library imports (e.g., `os`, `sys`, `pathlib`).
    2.  Third-party library imports (e.g., `numpy`, `pandas`, `typer`).
    3.  Local application/library specific imports (your own project's modules).

    ```python
    # =============================================================================
    # STANDARD LIBRARY IMPORTS
    # =============================================================================
    import pathlib
    import typing as t

    # =============================================================================
    # THIRD-PARTY IMPORTS
    # =============================================================================
    import numpy as np
    import pandas as pd
    from loguru import logger
    from pydantic import ConfigDict

    # =============================================================================
    # LOCAL APPLICATION IMPORTS
    # =============================================================================
    from ..utils import helper_function
    ```

- **Use Standard Aliases**: For widely-used libraries, adopt the community-standard aliases.
    - `import numpy as np`
    - `import pandas as pd`
    - `import lightning as L`
    - `import matplotlib.pyplot as plt`
    - `import multiprocessing as mp`
    - `import typing as t`
- **Avoid Wildcard Imports**: Never use `from module import *`.
- **Use Absolute Imports**: Prefer absolute imports (`from my_project.utils import helper`) over
  relative imports (`from ..utils import helper`).

### Documentation & Metadata

If it's not documented, it's harder to use and maintain.

- **Docstrings**: Write clear docstrings for all modules, classes, and functions using the **NumPy
  docstring standard**, as it clearly structures `parameters`, `returns`, `examples` (keep examples
  empty!), and `notes`.
- **Type Hinting**: Use Python's type hints for clarity and static analysis.
    * **Use the `|` operator for unions**: This modern syntax (fully supported in Python 3.11)
      enhances readability.
        * `str | int` replaces `Union[str, int]`.
        * `str | None` replaces `Optional[str]`.
    * For arguments that represent file paths, accept both `str` and `pathlib.Path` by using the
      type hint `str | pathlib.Path`.
- **Module Metadata**: Place module-level "dunder" variables (`__author__`, `__version__`, etc.)
  immediately after the module docstring.

    **Recommended Dunder Block:**
    ```python
    __author__ = "Yeremia Gunawan Adhisantoso"
    __email__ = "adhisant@tnt.uni-hannover.de"
    __license__ = "Clear BSD"
    __version__ = "1.0.0"
    ```
- **Use `#?` for Explanatory Comments**: Use inline comments prefixed with `#?` to explain the *why*
  behind complex or non-obvious code, not the *what*. The `?` prefix **is mandatory** for IDE syntax
  highlighting purposes.

### Versioning and Distribution

- **Semantic Versioning (SemVer)**: The project's version number (`__version__`) must follow the
  **Semantic Versioning** (`MAJOR.MINOR.PATCH`) standard.
- **Packaging**: Use a `pyproject.toml` file to define project metadata and dependencies for
  distributable packages.

### Logging

Good logging is essential for both user feedback and developer debugging.

- **Use a Logging Library**: Employ a library like `loguru` or the standard `logging` module.
- **Multiple Log Levels**: Use different log levels (`INFO`, `DEBUG`, `WARNING`, `ERROR`)
  appropriately.
- **Log Destinations**: For CLIs, log to both the console and a file. For other applications, a
  file-based logger is often sufficient. Console logs should be concise, while file logs should be
  verbose.

## Leveraging Python 3.11 for Performance & Modern Syntax
---

Python 3.11 introduces significant performance boosts and new syntax that should be leveraged.

### Performance Improvements
- **Interpreter Speedups**: Python 3.11 is **10-60% faster** than 3.10 on average. This comes for
  free without code changes due to a faster startup time and optimized function calls.
- **Specializing Adaptive Interpreter**: The interpreter now detects stable types and operations at
  runtime, replacing generic bytecode with faster, specialized versions automatically.

### New Syntax Features
- **Exception Group Handling (`except*`)**: Use the `except*` syntax to handle multiple, unrelated
  exceptions at once, which is especially useful in concurrent and asynchronous code.
- **Pattern Matching Enhancements**: Leverage updated structural pattern matching for clearer, more
  maintainable conditional logic compared to long `if/elif/else` chains.
- **Advanced Tuple Typing with Splat (`*`)**: Use `*` for more precise and flexible type annotations
  with variable-length tuples (e.g., `tuple[int, *tuple[str, ...]]`).

### Standard Library Features
- **`tomllib` Module**: Use the built-in `tomllib` to parse TOML files without requiring external
  dependencies, improving startup time and reliability.

## Application Logic & Reliability
---

### Architectural Principles
- **Separation of Concerns**: Break down logic into smaller, single-purpose functions or modules.
- **Configuration Management**: Use a library like `pydantic` to define, validate, and manage
  configuration from files or environment variables. Use the built-in `tomllib` for parsing TOML
  configuration files.

### Functional Design Patterns
- **Use Single Dispatch for Polymorphism**: Use `functools.singledispatch` to avoid complex
  `if/elif` chains based on an argument's type.
- **Use Decorators for Validation**: Use `pydantic`'s `@validate_call` decorator to enforce type
  hints and constraints at runtime.
- **Use Enums for Fixed Choices**: For parameters that accept a value from a fixed set, use the
  `enum` module. Prefer `enum.StrEnum` for string-based choices.

This example creates a robust enum that is both **case-insensitive** and supports **aliases** (e.g.,
"cat" for "categorical").

```python
from enum import StrEnum

class OptunaType(StrEnum):
    INT = "int"
    FLOAT = "float"
    LOGARITHM = "logarithm"
    CATEGORICAL = "categorical"

    @classmethod
    def _missing_(cls, value):
        if not isinstance(value, str):
            return super()._missing_(value)

        value_lower = value.lower()

        # 1. Handle special shorthand cases (aliases) first
        if value_lower == "log":
            return cls.LOGARITHM
        if value_lower == "cat":
            return cls.CATEGORICAL

        # 2. Handle general case-insensitive matching
        for member in cls:
            if member.value == value_lower:
                return member

        # 3. If no match is found, raise a helpful error
        valid_options = ", ".join(m.value for m in cls)
        raise ValueError(
            f"'{value}' is not a valid {cls.__name__}. "
            f"Please use one of: {valid_options}"
        )
```

### Robust Error Handling

- **Minimal `try` Blocks**: Keep the code inside a `try` block to the absolute minimum required.
  This prevents catching exceptions from unrelated code and makes the source of errors clearer.
- **Use Specific Exceptions**: Catch specific exceptions (e.g., `FileNotFoundError`) rather than a
  generic `Exception`.
- **Use Context Managers (`with`)**: For managing resources like files or network connections,
  always use a `with` statement to ensure resources are cleaned up reliably and automatically.
- **Provide Context**: When re-raising exceptions, add context to explain the operation. In Python
  3.11+, use the `add_note()` method on exceptions to add contextual information for improved
  debugging without altering the original exception type.
- **Custom Exceptions**: Define custom exception classes for application-specific errors.
- **Cleanup with `finally`**: Use `finally` blocks to ensure cleanup code always runs, especially
  when not using a context manager.

### Security Best Practices

- **Handle Sensitive Data**: Never hardcode secrets (API keys, passwords) in source code. Load them
  from environment variables or a dedicated secrets manager.
- **Input Sanitization**: Sanitize any input from untrusted sources to prevent injection attacks.
- **Safe Subprocesses**: Avoid using `shell=True` in the `subprocess` module with user-provided
  input.

## Class & Object-Oriented Design
---

Well-designed classes are the building blocks of a maintainable object-oriented program.

### Core Principles

- **Single Responsibility Principle**: A class should have only one reason to change. For example, a
  class that fetches data from an API should not also be responsible for formatting it into an HTML
  table. Keep classes focused on a single, well-defined purpose.
- **Use Dataclasses for Data Storage**: For classes that primarily exist to store data, use the
  `@dataclass` decorator (from the `dataclasses` module) or `pydantic` models. These automatically
  generate boilerplate methods like `__init__`, `__repr__`, and `__eq__`, leading to cleaner and
  more concise code.
- **Composition Over Inheritance**: Before using inheritance, consider if composition would be a
  better fit. Instead of having a class _be_ something (inheritance), have it _own_ something
  (composition). This often leads to more flexible and less coupled designs.

### Implementing Better Classes

- **Use `@property` for Controlled Access**: Use the `@property` decorator to expose a computed
  attribute as a read-only field.
- **Implement Dunder Methods for Usability**:
    - `__str__`: Provides a **user-friendly**, readable string representation.
    - `__repr__`: Provides an **unambiguous, developer-focused** string representation. The goal is
      for `eval(repr(obj))` to recreate the object.
    - `__eq__`: Defines equality (`==`) between two objects.

    ```python
    # Example using a dataclass, which provides __repr__ and __eq__ for free
    from dataclasses import dataclass

    @dataclass
    class User:
        username: str
        user_id: int

        def __str__(self) -> str:
            return f"User: {self.username}"

    # >>> user_one = User("alex", 101)
    # >>> print(user_one)
    # User: alex
    # >>> user_one
    # User(username='alex', user_id=101)
    ```

- **Referencing the Class Instance (`Self` Type)**: For methods that return an instance of their own
  class (e.g., for method chaining), use `typing.Self` as the return type hint. This is the modern,
  recommended way in Python 3.11+ to accurately express that a method returns an instance of the
  same type it was called on, which is invaluable for static analysis and IDE support.

    - **Example with Method Chaining**:
      ```python
      from typing import Self

      class Base:
          def set_value(self, x: int) -> Self:
              self.val = x
              return self

      class Derived(Base):
          def set_other(self, y: int) -> Self:
              self.other = y
              return self

      # The type of 'obj' is correctly inferred as 'Derived', allowing robust chaining.
      obj = Derived().set_value(10).set_other(20)
      ```

## Data Structure Best Practices
---

- **Choose the Right Built-in Type**:
    - **`list`**: Mutable, ordered sequence.
    - **`tuple`**: Immutable, ordered sequence for fixed data.
    - **`set`**: Unordered, unique items for fast membership testing.
    - **`dict`**: Key-value pairs for fast lookups.
- **Use Comprehensions**: Create lists, dictionaries, and sets concisely.
    ```python
    # Creates a list of squares for even numbers
    squares = [x**2 for x in range(10) if x % 2 == 0]
    # Creates a dictionary mapping names to their lengths
    name_lengths = {name: len(name) for name in ["alice", "bob", "charlie"]}
    ```

- **Leverage the `collections` Module**: For more advanced needs, use the specialized data
  structures in the `collections` module:
    - `collections.defaultdict`: A dictionary that provides a default value for a key that does not
      exist, preventing `KeyError`.
    - `collections.Counter`: A dictionary subclass for counting hashable objects. Excellent for
      frequency counts.
    - `collections.deque`: A "double-ended queue" that is highly optimized for adding and removing
      items from either end.

## Command-Line Interface (CLI) Specifics
---

A well-designed CLI is intuitive and provides clear feedback.
- **Argument Parsing**: Use a dedicated library like `Typer` or `Click`. These libraries
  automatically generate help messages (`--help`), handle input validation, and manage sub-commands.
- **Clear & Consistent Arguments**:
    - Clearly distinguish between mandatory positional arguments (e.g., `input_file`) and optional
      flags (e.g., `--output`).
    - Provide sensible defaults for optional arguments.
- **User Feedback**:
    - For long-running operations, provide a progress bar (e.g., with `tqdm`).
    - Print informative status messages to the console via a logger.
- **Safety Features**:
    - Provide a `--dry-run` (`-n`) option for any destructive operation.
    - When overwriting files, offer a `--backup` flag.

### Robust Logging and User Feedback
- **Use a Logging Library**: Employ a library like `loguru` for a simpler and more powerful logging
  experience.
- **Control Verbosity**: By default, show `INFO`-level logs. Use a `--verbose` (`-v`) flag to enable
  more detailed `DEBUG`-level logging.
- **Log to a File**: Configure logging to output to both the console (concise feedback) and a file
  (persistent, verbose records).

    ```python
    from loguru import logger
    import sys

    def setup_logging(verbose: bool):
        #? Configure logging for the CLI.
        logger.remove()
        log_level = "DEBUG" if verbose else "INFO"

        #? Concise console logger.
        logger.add(sys.stderr, level=log_level, format="<level>{message}</level>")

        #? Verbose file logger.
        logger.add(
            "logs/app.log",
            level="DEBUG",
            rotation="10 MB",
            retention="30 days",
            enqueue=True,
            backtrace=True,
            diagnose=True
        )
    ```

## Automated Testing & CI/CD
---

- **Testing Framework**: Use a standard testing framework like `unittest`.
- **Test Coverage**: Write tests for all new code, covering core logic, edge cases, and expected
  failures.
- **Test Location**: Keep tests in a dedicated `tests/` directory.

## Performance & Resource Management
---
### Performance-Conscious Code
- **Prefer Built-ins**: Use Python's built-in functions and operations (`sum()`, `len()`, etc.) as
  they often trigger specialized, faster bytecode.
- **Reduce Frame Creation**: Minimize unnecessary function call overhead by writing direct,
  thoughtful code and avoiding overly complex introspection patterns.
- **Simplify Function Calls**: Take advantage of Python 3.11's inlined function call optimizations
  by avoiding excessive functional indirection or dynamic dispatch where simple calls suffice.

### General Strategies
- **Parallel Processing**: For CPU-bound tasks, provide an option (e.g., `--jobs <N>` or `-j <N>`)
  to enable parallel processing using the `multiprocessing` module.
- **Memory Management**: Be mindful of memory usage with large files. Use generators and "lazy"
  loading where possible to process data in chunks rather than loading it all at once.
- **Caching**: Cache results of expensive computations or network requests using tools like
  `functools.lru_cache`.
- **High-Performance NumPy**:
    - **Vectorization**: Replace Python `for` loops with vectorized NumPy operations.
    - **Appropriate Data Types**: Use memory-efficient `dtype`s (e.g., `np.int32`).
    - **Just-In-Time Compilation**: For complex numerical algorithms, use `Numba` with the `@jit`
      decorator.
