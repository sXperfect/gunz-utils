# Installation

**Gunz-Utils** is the foundational core of the Pekora ecosystem, providing shared enums, validation logic, and project management utilities.

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
Gunz-Utils is designed to be lightweight. Its primary dependencies are `pydantic`, `rich`, and `GitPython`.
