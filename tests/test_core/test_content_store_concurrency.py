"""Concurrency regressions for content-addressed publication fallback."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import threading
import time
from pathlib import Path

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

import gunz_utils.content_store as content_store_module
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest
from gunz_utils.content_store import ContentAddressedStore


@pytest.mark.skipif(
    content_store_module.os.name not in {"posix", "nt"},
    reason="publication locking requires POSIX flock or Windows msvcrt",
)
def test_fallback_publication_serializes_cooperating_writers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    real_replace = content_store_module.os.replace
    first_replace_entered = threading.Event()
    allow_first_replace = threading.Event()
    counter_lock = threading.Lock()
    replace_calls = 0
    results = []
    errors: list[BaseException] = []

    def no_hardlinks(
        *_args: object,
        **_kwargs: object,
    ) -> None:
        raise OSError("hard links unavailable")

    def controlled_replace(
        source: Path | str,
        target: Path | str,
        *args: object,
        **kwargs: object,
    ) -> None:
        nonlocal replace_calls
        with counter_lock:
            replace_calls += 1
            call_number = replace_calls
        if call_number == 1:
            first_replace_entered.set()
            assert allow_first_replace.wait(3.0)
        real_replace(source, target, *args, **kwargs)

    def worker() -> None:
        try:
            results.append(store.put_bytes(b"same payload"))
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(content_store_module.os, "link", no_hardlinks)
    monkeypatch.setattr(content_store_module.os, "replace", controlled_replace)

    first = threading.Thread(target=worker)
    second = threading.Thread(target=worker)
    first.start()
    assert first_replace_entered.wait(3.0)

    second.start()
    time.sleep(0.05)
    with counter_lock:
        assert replace_calls == 1

    allow_first_replace.set()
    first.join(3.0)
    second.join(3.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert len(results) == 2
    assert results[0] == results[1]
    assert results[0].path.read_bytes() == b"same payload"
    with counter_lock:
        assert replace_calls == 1


def test_publication_lock_rejects_symlink(
    tmp_path: Path,
) -> None:
    target = tmp_path / "real.lock"
    target.write_bytes(b"x")
    link = tmp_path / "link.lock"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")

    with pytest.raises(ValueError, match="lock.*symlink"):
        with content_store_module._publication_lock(link):
            raise AssertionError("unreachable")
