# Quickstart

**Gunz-Utils** provides several critical primitives used across the 3D-Recon/Pekora projects.

## 1. Enhanced Enums

Use `BaseStrEnum` for case-insensitive string enums with fuzzy lookup support:

```python
from gunz_utils.enums import BaseStrEnum

class Mode(BaseStrEnum):
    TRAIN = "train"
    EVAL = "eval"

# Case insensitive lookup
mode = Mode.from_str("Train") 
print(mode)  # Mode.TRAIN
```

## 2. Project Management

Easily locate the project root and manage paths securely:

```python
from gunz_utils.project import get_project_root

root = get_project_root()
print(f"Project is located at: {root}")
```

## 3. Data Validation

Leverage Pydantic-powered validation for your research functions:

```python
from gunz_utils.validation import validate_call

@validate_call
def process_data(samples: int, resolution: int):
    print(f"Processing {samples} at {resolution}bp")

# This will raise a validation error if types are incorrect
process_data(samples=100, resolution=10000)
```
