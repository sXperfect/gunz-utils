# Best Practices for Python CLI Application Development
 _version: 1.6.0_

This document outlines a set of best practices and general requirements for developing robust,
usable, and maintainable command-line interface (CLI) applications in Python.

## Command-Line Interface (CLI) Design & User Interaction
---

A well-designed CLI is intuitive and provides clear feedback to the user.

* **Argument Parsing**: Use a dedicated library like `Typer` or `Click` to handle command-line
  arguments. These libraries automatically generate help messages and handle input validation.
* **Clear & Consistent Arguments**:
    * Clearly distinguish between mandatory positional arguments (e.g., `input_file`) and optional
      flags (e.g., `--output`).
    * Provide sensible defaults for optional arguments.
    * Use intuitive names for arguments and provide concise help text for each one.
    * Implement boolean flags like `--overwrite` or `--verbose` to control behavior simply.
* **Input/Output Handling**:
    * Clearly define how the application receives input and provides output (e.g., file paths,
      stdin/stdout).
    * If the script generates an output file, provide a default naming convention (e.g.,
      `<original_filename>.processed.ext`) but also allow the user to specify a custom output path
      with an `--output` (`-o`) flag.
* **User Feedback**:
    * For long-running operations, provide a progress bar (e.g., with `tqdm`) to show that the
      application is working.
    * Print informative status messages to the console (e.g., "Processing file X...", "Connecting to
      service Y...").
* **Safety by Default**: For any operation that makes changes to the filesystem or external systems,
  **implement a `--dry-run` mode (with a `-n` alias) whenever possible**. This critical feature
  simulates execution and reports the intended changes without actually performing them, giving
  users confidence and preventing costly mistakes.


## Application Logic, Structure & Reliability
---

The internal structure should be logical, robust, and easy to maintain.

* **Configuration Management**: For applications with multiple settings, use a library like
  `pydantic` to define, validate, and manage configuration. This centralizes settings and prevents
  invalid states.
* **Separation of Concerns**: Break down the application's logic into smaller, single-purpose
  functions or modules. For example, have separate functions for parsing arguments, processing data,
  and generating output.
* **Robust Error Handling**:
    * **Use Specific Exceptions**: Catch specific exceptions (e.g., `FileNotFoundError`,
      `ValueError`) rather than generic `Exception`. This prevents accidentally catching and
      silencing unrelated errors (like `KeyboardInterrupt`).
    * **Provide Context**: When catching and re-raising exceptions, add context to explain what the
      application was trying to do when the error occurred. This is invaluable for debugging.
    * **Custom Exceptions**: For application-specific errors (e.g., "InvalidDataFormatError"),
      define custom exception classes. This allows for more granular error handling in the code that
      calls your functions.
    * **User-Friendly Messages**: Log the full, detailed error to a file for developers, but present
      a clear, user-friendly message to the console that explains the problem and suggests a
      solution (e.g., "Error: Input file not found at path '...'. Please check the file path and try
      again.").
    * **Finally Block for Cleanup**: Use `finally` blocks to ensure that cleanup code (like closing
      files or database connections) runs regardless of whether an exception occurred.
* **Safety Features**:
    * Provide a `--dry-run` (short alias: `-n`) option for any destructive operation. This should
      simulate the actions and report what would have happened without making any actual changes.
        * **Typer Implementation Note**: When using `Typer`, it's common to end a dry-run path with
          `raise typer.Exit()`. Structure your code so this check occurs *before* the main
          `try...except` block for operational errors. Placing it inside a broad `try...except
          Exception:` block will cause the clean exit to be caught as an error, potentially allowing
          the application to proceed with the destructive operations you meant to avoid.
    * When overwriting files, offer a `--backup` flag that creates a copy of the original file
      before modification.


## Performance & Resource Management
---

Efficient applications respect the user's system resources.

* **Parallel Processing**: By default, the application should run sequentially. For tasks that are
  CPU-bound and can be broken down into independent units of work (e.g., processing many files),
  **provide an option (e.g., `--jobs <N>` or `-j <N>`) to enable parallel processing** using the
  `multiprocessing` module. This allows the user to explicitly request and configure the number of
  CPU cores to use. 🚀
* **Memory Management**: Be mindful of memory usage, especially when processing large files.
    * Use "backed" or "lazy" loading modes if available in libraries (like `scanpy`'s `backed='r'`).
    * Explicitly delete large objects (`del object_name`) and call the garbage collector
      (`gc.collect()`) in long-running loops or after processing large items within a
      multiprocessing context.
* **Caching**: For data that is expensive to fetch (e.g., from a network API), cache the results
  locally. On subsequent runs, check the cache first before re-fetching the data.
* **High-Performance NumPy**: When performing numerical computations, follow these practices:
    * **Vectorization**: Replace Python loops over array elements with vectorized NumPy operations.
      A single operation on a whole array (e.g., `array * 2`) is orders of magnitude faster than a
      `for` loop.
    * **Broadcasting**: Understand and use NumPy's broadcasting rules to perform operations on
      arrays of different but compatible shapes without creating unnecessary copies.
    * **Appropriate Data Types**: Use the most memory-efficient data type (`dtype`) for your data
      (e.g., `np.int32` instead of `np.int64` if your numbers fit). This reduces memory usage and
      can speed up computations.
    * **Avoid Unnecessary Copies**: Be aware of which NumPy operations return a copy of an array
      versus a view. Use in-place operations (e.g., `array += 1`) where appropriate to save memory.
    * **Just-In-Time Compilation**: For complex numerical algorithms that cannot be easily
      vectorized, use libraries like `Numba` to compile critical Python/NumPy code to fast machine
      code using a simple `@jit` decorator.


## Logging
---

Good logging is essential for both user feedback and developer debugging.

* **Default to `loguru` for Logging**: For its simplicity and powerful features, **`loguru` should
  be the default logging library**. Use Python's built-in `logging` module only when there is a
  specific reason or requirement to do so.
* **Multiple Log Levels**:
    * Use different log levels (`INFO`, `DEBUG`, `WARNING`, `ERROR`) appropriately.
    * By default, show `INFO`-level logs to the user.
    * To control verbosity, use a boolean flag like `--verbose` (with a short alias, `-v`). This
      flag should switch the logging level from the default (`INFO`) to `DEBUG` for troubleshooting.
      This approach is generally more user-friendly than requiring users to specify a log level by
      name (e.g., `--log-level DEBUG`).
* **Multiple Log Destinations**:
    * Configure logging to output to both the console (for immediate user feedback) and a file (for
      persistent, detailed records).
    * Console logs should be concise and human-readable.
    * File logs should be more verbose, including timestamps, function names, and line numbers.


## Dependency & Environment Management
---

A project should be reproducible and easy for others to set up.

* **Virtual Environments**: Always develop within a Python virtual environment (`venv`) to isolate
  project dependencies.
* **Declare Dependencies**: List all required third-party libraries in a `requirements.txt` file or,
  for more complex projects, a `pyproject.toml`.
* **Specify Python Version**: Clearly state the minimum required Python version (e.g., Python 3.8+)
  in the project's documentation (`README.md`).


## Code Quality & Maintainability
---

Writing clean, well-documented code is crucial for long-term success.

* **Module Metadata**: Place module-level "dunder" variables (e.g., `__author__`, `__version__`,
  `__status__`) immediately after the module docstring. This makes important metadata easily
  accessible to both developers and automated tools.
* **Type Hinting**: Use Python's type hints for function arguments and return values. This improves
  code clarity and allows for static analysis.
* **Docstrings and Comments**:
    * Write clear docstrings for all modules and functions. Use the **NumPy docstring standard**,
      which is comprehensive and well-suited for scientific and technical applications as it clearly
      structures parameters, returns, and examples.
    * Use inline comments to explain complex or non-obvious sections of code.
* **Code Formatting**: Use a consistent code style, enforced automatically with a tool like `Black`.
  Use a linter like `Flake8` or `Ruff` to catch common errors and style issues.
* **Standard Import Aliases**: To ensure consistency and readability, use standard,
  community-accepted aliases for common libraries.
    * `import numpy as np`
    * `import pandas as pd`
    * `import typing as t`
    * `import multiprocessing as mp`