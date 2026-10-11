"""Lease task-submission ownership regression."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import gc
import warnings
from collections.abc import Coroutine
from types import CoroutineType
from typing import Any

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.leases import run_with_lease_heartbeat


def test_rejected_heartbeat_coroutine_is_closed_by_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        baseline = asyncio.all_tasks()
        failure = RuntimeError("heartbeat rejected")
        rejected: list[Coroutine[Any, Any, None]] = []

        def reject(
            coroutine: Coroutine[Any, Any, None],
        ) -> asyncio.Task[None]:
            rejected.append(coroutine)
            raise failure

        async def operation() -> None:
            await asyncio.Event().wait()

        async def renew() -> bool:
            return True

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            with monkeypatch.context() as scope:
                scope.setattr(asyncio, "create_task", reject)
                with pytest.raises(RuntimeError) as observed:
                    await run_with_lease_heartbeat(
                        operation, renew, heartbeat_interval=1
                    )
            assert len(rejected) == 1
            assert isinstance(rejected[0], CoroutineType)
            assert rejected[0].cr_frame is None
            rejected.clear()
            gc.collect()
            await asyncio.sleep(0)
        assert observed.value is failure
        assert asyncio.all_tasks() == baseline
        assert not [w for w in captured if "never awaited" in str(w.message)]

    asyncio.run(scenario())
