"""Native recursion safety and integer-subclass semantic regressions."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils import binary, serialization


class ComparisonInteger(int):
    def __lt__(self,
        other: object,
    ) -> bool:
        return True


class ArithmeticInteger(int):
    def __and__(self,
        other: int,
    ) -> int:
        return 7


@pytest.mark.parametrize("value", [ComparisonInteger(3), ArithmeticInteger(3)])
def test_integer_subclass_preserves_reference_semantics(
    value: int,
) -> None:
    try:
        expected = binary._py_encode_uvarint(value)
    except ValueError as error:
        with pytest.raises(ValueError, match=str(error)):
            binary.encode_uvarint(value)
    else:
        assert binary.encode_uvarint(value) == expected


def test_default_depth_cycle_and_valid_tree_remain_bounded() -> None:
    cyclic: list[Any] = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="maximum nesting depth"):
        serialization.to_jsonable(cyclic)
    assert serialization.to_jsonable({"valid": [1, True, None]}) == {
        "valid": [1, True, None]
    }


@pytest.mark.parametrize("shape", ["cycle", "deep"])
def test_expanded_depth_raises_safely_in_isolated_interpreter(
    shape: str,
) -> None:
    """Run actual active backend with core dumps disabled and a bounded stack."""
    native_spec = importlib.util.find_spec("gunz_utils._accel")
    native_path = native_spec.origin if native_spec is not None else None
    source_root = Path(binary.__file__).resolve().parents[1]
    code = f"""
import importlib.util
import sys
try:
    import resource
except ImportError:
    pass
else:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_STACK, (1048576, 1048576))
sys.path.insert(0, {str(source_root)!r})
native_path = {native_path!r}
if native_path is None:
    sys.modules["gunz_utils._accel"] = None
else:
    spec = importlib.util.spec_from_file_location("gunz_utils._accel", native_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules["gunz_utils._accel"] = module
from gunz_utils import serialization
assert (serialization._accel_is_json_clean is not None) == (native_path is not None)
value = []
if {shape!r} == "cycle":
    value.append(value)
else:
    for _ in range(3000):
        value = [value]
try:
    serialization.to_jsonable(value, _max_depth=100000)
except RecursionError:
    print("controlled recursion error")
else:
    raise RuntimeError("expanded depth was not rejected")
assert serialization.to_jsonable({{"still": [1, 2]}}) == {{"still": [1, 2]}}
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, (result.returncode, result.stderr)
    assert result.stdout.strip() == "controlled recursion error"


def test_deep_valid_input_retains_reference_semantics_beyond_fast_path() -> None:
    value: Any = "leaf"
    for _ in range(200):
        value = [value]
    if serialization._accel_is_json_clean is not None:
        assert serialization._accel_is_json_clean(value, 100000) is False
    result = serialization.to_jsonable(value, _max_depth=100000)
    for _ in range(200):
        assert isinstance(result, list)
        assert len(result) == 1
        result = result[0]
    assert result == "leaf"
