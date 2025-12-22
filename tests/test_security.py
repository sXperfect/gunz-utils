# -*- coding: utf-8 -*-
import pytest
from gunz_utils.security import sanitize_filename, safe_path_join
import os

def test_sanitize_filename_valid():
    """Test standard valid filenames."""
    assert sanitize_filename("test_file.txt") == "test_file.txt"
    assert sanitize_filename("image-123.png") == "image-123.png"
    assert sanitize_filename("MyFile.JPG") == "MyFile.JPG"

def test_sanitize_filename_path_traversal():
    """Test protection against path traversal."""
    # os.path.basename handles the slashes, our regex handles the rest
    assert sanitize_filename("../../etc/passwd") == "passwd"

    # ".." -> basename ".." -> strip dots -> empty -> ValueError
    with pytest.raises(ValueError, match="Filename is empty"):
        sanitize_filename("..")

    with pytest.raises(ValueError, match="Filename is empty"):
        sanitize_filename(".")

def test_sanitize_filename_dangerous_chars():
    """Test removal of dangerous characters."""
    # ? -> _
    # * -> _
    # file?name*.txt -> file_name_.txt
    assert sanitize_filename("file?name*.txt") == "file_name_.txt"
    assert sanitize_filename("file<name>.txt") == "file_name_.txt"
    assert sanitize_filename("file|name.txt") == "file_name.txt"
    assert sanitize_filename("file:name.txt") == "file_name.txt"

def test_sanitize_filename_spaces():
    """Test handling of spaces."""
    assert sanitize_filename("my file name.txt") == "my_file_name.txt"
    assert sanitize_filename("my   file.txt") == "my_file.txt"

def test_sanitize_filename_strip():
    """Test stripping of dots and replacements."""
    assert sanitize_filename(".hidden") == "hidden"
    assert sanitize_filename("_start") == "start"
    assert sanitize_filename("end_") == "end"
    assert sanitize_filename("file.") == "file"

def test_sanitize_filename_empty():
    """Test empty input."""
    with pytest.raises(ValueError):
        sanitize_filename("")
    with pytest.raises(ValueError):
        sanitize_filename("   ")
    with pytest.raises(ValueError):
        sanitize_filename("///")

def test_sanitize_filename_length():
    """Test length truncation."""
    long_name = "a" * 300
    sanitized = sanitize_filename(long_name)
    assert len(sanitized) == 255
    assert sanitized == "a" * 255

def test_sanitize_filename_windows_reserved():
    """Test handling of Windows reserved filenames."""
    reserved = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
    for name in reserved:
        # Should now be prefixed with underscore
        assert sanitize_filename(name) == f"_{name}"
        assert sanitize_filename(f"{name}.txt") == f"_{name}.txt"
        assert sanitize_filename(f"{name}.tar.gz") == f"_{name}.tar.gz"

        # Case insensitive check
        assert sanitize_filename(name.lower()) == f"_{name.lower()}"


def test_safe_path_join_valid(tmp_path):
    """Test valid path joins."""
    # Use tmp_path to ensure we have a valid, resolvable base directory
    base = str(tmp_path)
    # resolve base to handle any symlinks in tmp path itself (e.g. /var vs /private/var)
    base = os.path.realpath(base)

    expected = os.path.join(base, "uploads", "image.png")
    assert safe_path_join(base, "uploads", "image.png") == expected

    expected_css = os.path.join(base, "static", "css")
    assert safe_path_join(base, "static/css") == expected_css

def test_safe_path_join_traversal(tmp_path):
    """Test path traversal detection."""
    base = os.path.realpath(str(tmp_path))

    with pytest.raises(ValueError, match="Path traversal detected"):
        safe_path_join(base, "../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        # Note: we use os.path.join to construct the traversal string properly for the OS if needed,
        # but ".." is standard.
        safe_path_join(base, "uploads/../../etc/passwd")

def test_safe_path_join_absolute_input(tmp_path):
    """Test handling of absolute inputs (should be treated as relative)."""
    base = os.path.realpath(str(tmp_path))

    # Construct an absolute path. On Linux /etc/passwd, on Windows C:\etc\passwd
    abs_input = os.path.abspath(os.path.join(os.sep, "etc", "passwd"))

    # Our implementation treats absolute paths as relative by stripping the root
    # So /etc/passwd becomes etc/passwd inside base
    # We must replicate the stripping logic to assert correctly

    # Expected behavior:
    # 1. splitdrive (handles C:)
    # 2. lstrip sep
    # 3. join to base

    _, rel = os.path.splitdrive(abs_input)
    rel = rel.lstrip(os.path.sep)
    expected = os.path.join(base, rel)

    assert safe_path_join(base, abs_input) == expected

def test_safe_path_join_null_bytes(tmp_path):
    """Test null byte injection."""
    base = os.path.realpath(str(tmp_path))
    with pytest.raises(ValueError, match="Null byte found"):
        safe_path_join(base, "image.png\0.php")
