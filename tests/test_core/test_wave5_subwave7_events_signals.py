"""Tests for Wave 5 Sub-Wave 7: Event Bus, Signals & Observer Patterns."""

import asyncio
import time
import pytest

from gunz_utils.events import (
    AsyncEvent,
    EventBus,
    SignalObserver,
    debounce,
    throttle,
)


def test_event_bus_sync():
    bus = EventBus()
    received = []

    def handler(msg):
        received.append(msg)
        return f"ack:{msg}"

    unsub = bus.subscribe("greeting", handler)
    res = bus.publish("greeting", "hello")
    assert res == ["ack:hello"]
    assert received == ["hello"]

    # Test unsubscribe
    unsub()
    res2 = bus.publish("greeting", "world")
    assert res2 == []
    assert received == ["hello"]


def test_event_bus_subscribe_once():
    bus = EventBus()
    calls = []

    bus.subscribe_once("tick", lambda x: calls.append(x))
    bus.publish("tick", 1)
    bus.publish("tick", 2)
    assert calls == [1]


def test_event_bus_error_policy():
    errors = []

    def on_error(exc, topic):
        errors.append((type(exc).__name__, topic))

    bus = EventBus(on_error=on_error)

    def failing():
        raise RuntimeError("boom")

    def ok():
        return 42

    bus.subscribe("topic1", failing)
    bus.subscribe("topic1", ok)

    res = bus.publish("topic1")
    assert res == [42]
    assert errors == [("RuntimeError", "topic1")]


@pytest.mark.asyncio
async def test_event_bus_async():
    bus = EventBus()
    received = []

    async def async_handler(val):
        await asyncio.sleep(0.01)
        received.append(val)
        return val * 2

    bus.subscribe("calc", async_handler)
    res = await bus.publish_async("calc", 5)
    assert res == [10]
    assert received == [5]


def test_signal_observer():
    obs = SignalObserver(10)
    history = []

    unsub = obs.subscribe(lambda old, new: history.append((old, new)))
    obs.value = 20
    obs.value = 20  # no change
    obs.value = 30
    assert history == [(10, 20), (20, 30)]

    unsub()
    obs.value = 40
    assert history == [(10, 20), (20, 30)]


@pytest.mark.asyncio
async def test_async_event():
    ev = AsyncEvent()
    assert not ev.is_set()

    # Timeout case
    res = await ev.wait_with_timeout(timeout=0.01)
    assert not res

    ev.set()
    assert ev.is_set()
    res2 = await ev.wait_with_timeout(timeout=0.1)
    assert res2

    ev.clear()
    assert not ev.is_set()


def test_throttle():
    called = 0

    @throttle(0.05)
    def inc():
        nonlocal called
        called += 1
        return called

    assert inc() == 1
    assert inc() == 1  # throttled
    time.sleep(0.06)
    assert inc() == 2


def test_debounce():
    called = 0

    @debounce(0.05)
    def ping():
        nonlocal called
        called += 1

    ping()
    ping()
    ping()
    # Not executed yet
    assert called == 0
    time.sleep(0.08)
    assert called == 1
