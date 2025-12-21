# -*- coding: utf-8 -*-
import pytest
from gunz_utils.security import sanitize_filename

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
