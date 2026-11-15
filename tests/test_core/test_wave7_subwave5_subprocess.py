"""Tests for Wave 7 Sub-Wave 5: Safe System Process & Subprocess Streaming."""

import sys
from gunz_utils.subprocess import (
    clean_subprocess_env,
    find_open_port,
    is_executable,
    is_port_in_use,
    stream_command_output,
    which,
)


def test_which_and_is_executable():
    python_path = which("python3") or which("python")
    assert python_path is not None
    assert is_executable(python_path)


def test_find_and_test_open_port():
    port = find_open_port(start_port=12000, max_tries=50)
    assert 12000 <= port < 12050
    assert not is_port_in_use(port)


def test_clean_subprocess_env():
    env = clean_subprocess_env(extra_env={"CUSTOM_KEY": "CUSTOM_VAL"}, remove_keys=["PATH"])
    assert env.get("CUSTOM_KEY") == "CUSTOM_VAL"
    assert "PATH" not in env


def test_stream_command_output():
    cmd = [sys.executable, "-c", "print('hello'); import sys; print('world', file=sys.stderr)"]
    lines = list(stream_command_output(cmd))
    outputs = [(tag, line.strip()) for _, tag, line in lines]
    assert ("stdout", "hello") in outputs
    assert ("stderr", "world") in outputs
