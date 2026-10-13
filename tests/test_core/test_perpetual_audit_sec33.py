"""Perpetual security audit phase 33 (round 4, deepest).

Re-audit of ``dict_utils``, ``collections``, ``signals``, ``sync``, and
``time_utils``.

Findings:

1. ``signals.GracefulShutdown.__aexit__`` runs registered cleanup callbacks
   only when shutdown was triggered or the enclosing task was cancelled
   (signals.py:425 ``if self.is_shutting_down or is_cancelled``).  When the
   ``async with`` body exits via an ordinary exception, or completes normally
   without an explicit shutdown, the cleanup callbacks registered through
   ``add_callback`` are never invoked, so resources they are responsible for
   releasing leak.  Cancellation runs cleanup, but a body exception -- the
   path where cleanup is arguably most important -- silently skips it.  A
   coordinated shutdown/cleanup coordinator must run its callbacks on every
   exit (shutdown, cancellation, body exception, and normal completion) while
   still propagating the original body exception.

2. ``sync._normalize_rsync_source`` passes remote-source path parts verbatim
   to rsync's remote shell (sync.py:24, 146-165).  A local source is validated
   (leading-dash and control-character rejection) and resolved, but a string
   matching the remote syntax ``^[^/\\:]+:.+$`` is returned unchanged.  rsync
   feeds that path into a remote shell (ssh/rsh), so a source such as
   ``user@host:/x;touch /tmp/pwn`` executes ``touch /tmp/pwn`` on the remote
   host.  This contradicts the module's own "Shell-free rsync directory
   mirroring" guarantee and enables remote command injection whenever the
   source is derived from untrusted input.  Remote-source paths must reject
   shell metacharacters (``; | & \\` $ \\n`` and friends), consistent with the
   validation applied to local sources.

The remaining GREEN coverage pins correct behavior so the fixes cannot
regress: GracefulShutdown runs cleanup on cancellation and propagates
exceptions, rsync option-injection filtering and source/target/timeout
validation hold, dict_utils merge/get/set semantics and cycle safety hold,
collections helpers stay correct, and time_utils bound validation holds.
"""

import asyncio

import pytest

from gunz_utils import collections, dict_utils, signals, sync, time_utils

# ---------------------------------------------------------------------------
# Finding 1: GracefulShutdown skips cleanup on body exception / normal exit
# ---------------------------------------------------------------------------


def test_graceful_shutdown_runs_cleanup_on_body_exception():
    """RED: when the ``async with`` body raises an ordinary exception, the
    registered cleanup callbacks must still run (resource safety).  Currently
    cleanup is skipped because the exception is neither a shutdown trigger nor
    a cancellation.
    """

    async def scenario() -> list[str]:
        ran: list[str] = []
        coordinator = signals.GracefulShutdown()

        async def body() -> None:
            async with coordinator as gs:
                gs.add_callback(lambda: ran.append("cleanup"))
                raise RuntimeError("body boom")

        try:
            await body()
        except RuntimeError:
            pass
        return ran

    assert asyncio.run(scenario()) == ["cleanup"]


def test_graceful_shutdown_runs_cleanup_on_normal_completion():
    """RED: when the ``async with`` body completes normally without an
    explicit shutdown, the registered cleanup callbacks must still run.
    Currently they are skipped.
    """

    async def scenario() -> list[str]:
        ran: list[str] = []
        coordinator = signals.GracefulShutdown()
        async with coordinator as gs:
            gs.add_callback(lambda: ran.append("cleanup"))
        return ran

    assert asyncio.run(scenario()) == ["cleanup"]


# ---------------------------------------------------------------------------
# Finding 2: sync remote-source path allows shell-metacharacter injection
# ---------------------------------------------------------------------------


def test_rsync_source_rejects_shell_metacharacters_in_remote_path():
    """RED: a remote-source path containing shell metacharacters must be
    rejected.  Currently ``user@host:/x;touch /tmp/pwn`` is returned verbatim
    (sync.py:158), which rsync would feed to a remote shell.
    """
    with pytest.raises(ValueError):
        sync._normalize_rsync_source("user@host:/x;touch /tmp/pwn")


# ---------------------------------------------------------------------------
# GREEN: GracefulShutdown / signals correctness that must not regress
# ---------------------------------------------------------------------------


def test_graceful_shutdown_runs_cleanup_on_cancellation():
    """GREEN: cancellation runs cleanup callbacks (already-correct path)."""

    async def scenario() -> list[str]:
        ran: list[str] = []
        coordinator = signals.GracefulShutdown()
        task = asyncio.create_task(_wait_long(coordinator, ran))
        await asyncio.sleep(0.02)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return ran

    async def _wait_long(coordinator, ran) -> None:
        async with coordinator as gs:
            gs.add_callback(lambda: ran.append("cleanup"))
            await asyncio.sleep(10)

    assert asyncio.run(scenario()) == ["cleanup"]


def test_graceful_shutdown_collects_callback_exceptions():
    """GREEN: run_cleanup collects ordinary exceptions from callbacks instead
    of aborting the remaining cleanup.
    """

    async def scenario() -> None:
        coordinator = signals.GracefulShutdown()
        coordinator.add_callback(lambda: (_ for _ in ()).throw(RuntimeError("cb")))
        coordinator.add_callback(lambda: "ok")
        errors = await coordinator.run_cleanup()
        assert len(errors) == 1
        assert isinstance(errors[0][1], RuntimeError)

    asyncio.run(scenario())


def test_graceful_shutdown_trigger_and_wait():
    """GREEN: trigger_shutdown sets the event and wait_for_shutdown returns the
    recorded signal number.
    """

    async def scenario() -> None:
        coordinator = signals.GracefulShutdown()
        coordinator.trigger_shutdown(signum=15)
        assert await coordinator.wait_for_shutdown() == 15
        assert coordinator.is_shutting_down is True

    asyncio.run(scenario())


def test_graceful_shutdown_timeout_validation():
    """GREEN: invalid timeout values are rejected with ValueError."""
    for bad in (True, "5", 0, -1, float("inf"), 10**400):
        with pytest.raises(ValueError):
            signals.GracefulShutdown(timeout=bad)  # type: ignore[arg-type]


def test_install_termination_handler_validates_inputs():
    """GREEN: invalid callback/signum/exit_after are rejected."""
    with pytest.raises(TypeError):
        signals.install_termination_handler("not-callable")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        signals.install_termination_handler(lambda s: None, signum=0)
    with pytest.raises(ValueError):
        signals.install_termination_handler(lambda s: None, signum=1, exit_after="x")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: sync validation that must not regress
# ---------------------------------------------------------------------------


def test_sync_rejects_destructive_and_execution_options():
    """GREEN: destructive/execution-affecting rsync options (and abbreviations)
    are rejected through extra_args; benign options are allowed.
    """
    for dangerous in (
        "--delete",
        "--del",
        "--temp-dir=/x",
        "--temp=/x",
        "--rsh",
        "-e",
        "-e ssh",
        "-aT",
        "--exclude=!",
        "--include=!",
        "--excl=!",
    ):
        assert sync._unsafe_rsync_extra_argument(dangerous) is True
    for benign in ("--backup", "--partial", "-B100", "--exclude=*.tmp"):
        assert sync._unsafe_rsync_extra_argument(benign) is False


def test_sync_source_rejects_leading_dash_and_control_characters():
    """GREEN: local-source validation rejects option-injection and control chars."""
    with pytest.raises(ValueError):
        sync._normalize_rsync_source("-flag")
    with pytest.raises(ValueError):
        sync._normalize_rsync_source("bad\nsource")


def test_sync_timeout_validation():
    """GREEN: invalid timeout values are rejected with ValueError."""
    with pytest.raises(ValueError):
        sync.rsync_mirror("/x", "/y", timeout=10**400)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        sync.rsync_mirror("/x", "/y", timeout=float("inf"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        sync.rsync_mirror("/x", "/y", timeout=0)


def test_sync_extra_args_must_be_nonempty_strings():
    """GREEN: extra_args entries are validated."""
    with pytest.raises(ValueError):
        sync.rsync_mirror("/x", "/y", extra_args=[""])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# GREEN: dict_utils semantics and cycle safety that must not regress
# ---------------------------------------------------------------------------


def test_deep_merge_override_semantics_and_cycle_safety():
    """GREEN: override wins for scalars, dicts recurse, and cyclic inputs merge
    without infinite recursion.
    """
    assert dict_utils.deep_merge({"a": 1}, {"a": 2, "b": 3}) == {
        "a": 2,
        "b": 3,
    }
    assert dict_utils.deep_merge({"x": {"y": 1}}, {"x": {"z": 2}})["x"] == {
        "y": 1,
        "z": 2,
    }
    cyclic: dict[object, object] = {}
    cyclic["self"] = cyclic
    result = dict_utils.deep_merge(cyclic, {"self": {"k": 1}, "n": 2})
    assert result["n"] == 2
    assert result["self"]["k"] == 1


def test_deep_merge_list_strategies():
    """GREEN: list strategies replace/concat/dedup behave as documented."""
    base = {"xs": [1, 2, 3]}
    assert dict_utils.deep_merge(base, {"xs": [3]})["xs"] == [3]
    assert dict_utils.deep_merge(base, {"xs": [4]}, list_strategy="concat")["xs"] == [
        1,
        2,
        3,
        4,
    ]
    assert dict_utils.deep_merge(base, {"xs": [2, 4]}, list_strategy="dedup")["xs"] == [
        1,
        2,
        3,
        4,
    ]
    with pytest.raises(ValueError):
        dict_utils.deep_merge(base, {"xs": [4]}, list_strategy="bogus")  # type: ignore[arg-type]


def test_deep_get_set_semantics():
    """GREEN: deep_get returns defaults/missing KeyError; deep_set creates paths."""
    data = {"a": {"b": 1}}
    assert dict_utils.deep_get(data, "a.b") == 1
    assert dict_utils.deep_get(data, "a.missing", default=None) is None
    with pytest.raises(KeyError):
        dict_utils.deep_get(data, "a.missing")
    target: dict[str, object] = {}
    dict_utils.deep_set(target, "x.y.z", 42)
    assert target == {"x": {"y": {"z": 42}}}


def test_deep_path_rejects_empty_segments():
    """GREEN: paths with empty segments or no segments are rejected."""
    with pytest.raises(ValueError):
        dict_utils.deep_get({"a": 1}, "a..b")
    with pytest.raises(ValueError):
        dict_utils.deep_get({"a": 1}, [])


# ---------------------------------------------------------------------------
# GREEN: collections helpers that must not regress
# ---------------------------------------------------------------------------


def test_unique_preserves_order_and_handles_unhashable():
    """GREEN: unique keeps first occurrences; unhashable items dedup by equality."""
    assert collections.unique([3, 1, 3, 2, 1]) == [3, 1, 2]
    assert collections.unique([[1], [2], [1]]) == [[1], [2]]
    assert collections.unique([{"k": 1}, {"k": 1}, {"k": 2}], key=lambda d: d["k"]) == [
        {"k": 1},
        {"k": 2},
    ]


def test_group_by_index_by_partition():
    """GREEN: grouping/indexing/partitioning behave as documented."""
    assert collections.group_by([1, 2, 3, 4], key=lambda n: n % 2) == {
        1: [1, 3],
        0: [2, 4],
    }
    assert collections.index_by(["a", "ab", "abc"], key=len) == {
        1: "a",
        2: "ab",
        3: "abc",
    }
    yes, no = collections.partition(range(5), lambda n: n % 2 == 0)
    assert yes == [0, 2, 4]
    assert no == [1, 3]


# ---------------------------------------------------------------------------
# GREEN: time_utils bound validation that must not regress
# ---------------------------------------------------------------------------


def test_monotonic_deadline_rejects_invalid_timeout():
    """GREEN: bool/non-numeric/inf/nan/negative/huge timeouts are rejected."""
    for bad in (True, "5", float("inf"), float("nan"), -1, 10**400):
        with pytest.raises(ValueError):
            time_utils.monotonic_deadline(bad)  # type: ignore[arg-type]


def test_remaining_and_expired_semantics():
    """GREEN: remaining is non-negative; expired is True for past deadlines."""
    now = time_utils.monotonic_deadline(100.0)
    assert time_utils.remaining(now) >= 0
    assert time_utils.expired(now) is False
    assert time_utils.remaining(now - 1000.0) == 0.0
    assert time_utils.expired(now - 1000.0) is True
