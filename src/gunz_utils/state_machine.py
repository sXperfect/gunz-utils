"""Declarative finite state machine with guards, lifecycle hooks, and transition
history.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any


class InvalidTransitionError(RuntimeError):
    """Raised when an illegal state transition is triggered."""


@dataclass(slots=True)
class State:
    """Represents a discrete state within a finite state machine."""

    name: str
    on_enter: Callable[..., Any] | None = None
    on_exit: Callable[..., Any] | None = None


@dataclass(slots=True)
class Transition:
    """Represents an edge between states governed by an event trigger."""

    trigger: str
    source: tuple[str, ...]
    target: str
    guard: Callable[..., bool] | None = None
    action: Callable[..., Any] | None = None


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    """Immutable audit entry for a state transition."""

    trigger: str
    source: str
    target: str
    timestamp: float


class StateMachine:
    """Deterministic finite state machine with transition guards and history."""

    def __init__(self,
        initial_state: str,
    ) -> None:
        if not isinstance(initial_state, str) or not initial_state:
            raise ValueError("initial_state must be a non-empty string")
        self._initial_state = initial_state
        self._current_state = initial_state
        self._states: dict[str, State] = {initial_state: State(initial_state)}
        self._transitions: list[Transition] = []
        self._history: list[TransitionRecord] = []

    @property
    def current_state(self) -> str:
        """Return the current active state."""
        return self._current_state

    @property
    def history(self) -> list[TransitionRecord]:
        """Return a copy of the transition history log."""
        return list(self._history)

    def add_state(self,
        name: str,
        *,
        on_enter: Callable[..., Any] | None = None,
        on_exit: Callable[..., Any] | None = None,
    ) -> StateMachine:
        """Register a new state or configure lifecycle callbacks."""
        if not isinstance(name, str) or not name:
            raise ValueError("state name must be a non-empty string")
        self._states[name] = State(name=name, on_enter=on_enter, on_exit=on_exit)
        return self

    def add_transition(self,
        trigger: str,
        source: str | Sequence[str],
        target: str,
        *,
        guard: Callable[..., bool] | None = None,
        action: Callable[..., Any] | None = None,
    ) -> StateMachine:
        """Define a valid state transition triggered by an event."""
        if not isinstance(trigger, str) or not trigger:
            raise ValueError("trigger must be a non-empty string")
        if isinstance(source, str):
            sources: tuple[str, ...] = (source,)
        else:
            sources = tuple(source)
            if not sources:
                raise ValueError("source must contain at least one state name")

        for s in sources:
            if s not in self._states:
                self.add_state(s)
        if target not in self._states:
            self.add_state(target)

        self._transitions.append(
            Transition(
                trigger=trigger,
                source=sources,
                target=target,
                guard=guard,
                action=action,
            )
        )
        return self

    def can_trigger(self,
        trigger: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """Check if trigger can be executed from current state with given arguments."""
        for t in self._transitions:
            if t.trigger == trigger and self._current_state in t.source:
                if t.guard is None or t.guard(*args, **kwargs):
                    return True
        return False

    def trigger(self,
        trigger: str,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """Execute a state transition. Raises InvalidTransitionError if unauthorized."""
        matching_transition: Transition | None = None
        for t in self._transitions:
            if t.trigger == trigger and self._current_state in t.source:
                if t.guard is None or t.guard(*args, **kwargs):
                    matching_transition = t
                    break

        if matching_transition is None:
            raise InvalidTransitionError(
                f"cannot trigger {trigger!r} from current state {self._current_state!r}"
            )

        source_state_obj = self._states[self._current_state]
        target_state_obj = self._states[matching_transition.target]

        # 1. Execute on_exit of old state
        if source_state_obj.on_exit is not None:
            source_state_obj.on_exit(*args, **kwargs)

        # 2. Execute transition action
        if matching_transition.action is not None:
            matching_transition.action(*args, **kwargs)

        # 3. Update state
        old_state = self._current_state
        self._current_state = matching_transition.target
        self._history.append(
            TransitionRecord(
                trigger=trigger,
                source=old_state,
                target=self._current_state,
                timestamp=time.time(),
            )
        )

        # 4. Execute on_enter of new state
        if target_state_obj.on_enter is not None:
            target_state_obj.on_enter(*args, **kwargs)

        return True

    def reset(self,
        state: str | None = None,
    ) -> None:
        """Reset the state machine to initial or specified state."""
        target = self._initial_state if state is None else state
        if target not in self._states:
            raise ValueError(f"unknown state: {target}")
        self._current_state = target
        self._history.clear()


__all__ = [
    "InvalidTransitionError",
    "State",
    "StateMachine",
    "Transition",
    "TransitionRecord",
]
