# Gunz Utils

[![CI](https://github.com/sXperfect/gunz-utils/actions/workflows/ci.yml/badge.svg)](https://github.com/sXperfect/gunz-utils/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE.md)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)

**Gunz Utils** is a robust collection of general-purpose Python utilities designed for production environments. Currently, it features a powerful set of enhanced Enum classes that solve common pain points in Python's standard `enum` library.

## Features

### Enhanced Enums (`gunz_utils.enums`)

The `BaseStrEnum` and `BaseIntEnum` classes provide significant improvements over standard Python Enums:

*   **Fuzzy Matching**: Lookup members by case-insensitive name, value, or normalized string (ignoring separators like `-` and `_`).
*   **Alias Support**: Define robust aliases for your enum members using `__ALIASES__`.
*   **Safe Lookup**: Use `get_or_none()` to safely retrieve members without raising exceptions.
*   **Introspection**: Helper methods like `names()`, `values()`, and `items()` for cleaner code.
*   **CLI Integration**: `choices()` method to generate valid options for CLI tools (Click, Typer, argparse).

## Installation

### From GitHub (Pip)

You can install the latest version directly from the repository:

```bash
pip install git+https://github.com/sXperfect/gunz-utils.git
```

### From Source (Editable)

For development or local integration:

```bash
git clone https://github.com/sXperfect/gunz-utils.git
cd gunz-utils
pip install -e .
```

## Usage

### Enhanced String Enum

```python
from gunz_utils.enums import BaseStrEnum

class Color(BaseStrEnum):
    # Define aliases (optional)
    __ALIASES__ = {"crimson": "red", "dark": "dark_blue"}
    
    RED = "red"
    BLUE = "blue"
    DARK_BLUE = "dark_blue"

# 1. Fuzzy Lookup (Case/Separator Insensitive)
print(Color.from_fuzzy_string("dark-blue"))  # Color.DARK_BLUE
print(Color.from_fuzzy_string("RED"))        # Color.RED

# 2. Alias Lookup
print(Color.from_fuzzy_string("crimson"))    # Color.RED

# 3. Safe Lookup
print(Color.get_or_none("purple"))           # None

# 4. Introspection
print(Color.names())   # ['RED', 'BLUE', 'DARK_BLUE']
print(Color.values())  # ['red', 'blue', 'dark_blue']
```

### Enhanced Integer Enum

```python
from gunz_utils.enums import BaseIntEnum

class HttpStatus(BaseIntEnum):
    __ALIASES__ = {"missing": 404, "ok": 200}
    
    OK = 200
    NOT_FOUND = 404

# String-to-Int conversion with alias support
print(HttpStatus.from_fuzzy_int_string("missing"))  # HttpStatus.NOT_FOUND
print(HttpStatus.from_fuzzy_int_string("404"))      # HttpStatus.NOT_FOUND
```

## Development

To run the test suite:

```bash
python -m unittest discover tests
```

## License

This project is licensed under the Clear BSD License - see the [LICENSE.md](LICENSE.md) file for details.

Copyright (c) 2025-present, Yeremia Gunawan Adhisantoso (sXperfect).