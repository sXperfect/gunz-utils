"""Tests for Wave 6 Sub-Wave 2: Declarative Finite State Machine."""

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.state_machine import (
    InvalidTransitionError,
    StateMachine,
)


def test_state_machine_basic_flow():
    events_log = []

    fsm = StateMachine(initial_state="draft")
    fsm.add_state("draft", on_exit=lambda: events_log.append("exit_draft"))
    fsm.add_state("published", on_enter=lambda: events_log.append("enter_published"))

    fsm.add_transition("publish", source="draft", target="published",
                       action=lambda: events_log.append("publishing"))

    assert fsm.current_state == "draft"
    assert fsm.can_trigger("publish")
    assert not fsm.can_trigger("archive")

    fsm.trigger("publish")
    assert fsm.current_state == "published"
    assert events_log == ["exit_draft", "publishing", "enter_published"]
    assert len(fsm.history) == 1
    assert fsm.history[0].trigger == "publish"
    assert fsm.history[0].source == "draft"
    assert fsm.history[0].target == "published"


def test_state_machine_guard():
    fsm = StateMachine("locked")
    fsm.add_transition(
        "unlock",
        source="locked",
        target="unlocked",
        guard=lambda key: key == "secret",
    )

    assert not fsm.can_trigger("unlock", key="wrong")
    assert fsm.can_trigger("unlock", key="secret")

    with pytest.raises(InvalidTransitionError):
        fsm.trigger("unlock", key="wrong")

    fsm.trigger("unlock", key="secret")
    assert fsm.current_state == "unlocked"


def test_state_machine_multiple_sources_and_reset():
    fsm = StateMachine("active")
    fsm.add_transition(
    "terminate",
    source=[
        "active",
        "paused",
        "errored"],
         target="stopped")

    assert fsm.current_state == "active"
    fsm.trigger("terminate")
    assert fsm.current_state == "stopped"

    fsm.reset("active")
    assert fsm.current_state == "active"
    assert len(fsm.history) == 0
