"""Tests for generic allow/deny name policies."""

from __future__ import annotations

import pytest

from gunz_utils.security import NameAccessPolicy


def test_name_access_policy_allows_by_default() -> None:
    policy = NameAccessPolicy()

    assert policy.allows("provider")
    assert policy.check("provider")


def test_name_access_policy_deny_takes_precedence() -> None:
    policy = NameAccessPolicy(
        allowed=frozenset({"safe", "blocked"}),
        denied=frozenset({"blocked"}),
    )

    assert policy.allows("safe")
    assert not policy.allows("blocked")

    with pytest.raises(PermissionError, match="explicitly denied"):
        policy.check("blocked")


def test_name_access_policy_enforces_allowlist() -> None:
    policy = NameAccessPolicy(
        allowed=frozenset({"safe"}),
    )

    assert policy.allows("safe")
    assert not policy.allows("other")

    with pytest.raises(PermissionError, match="not allowlisted"):
        policy.check("other")


def test_name_access_policy_rejects_empty_names() -> None:
    policy = NameAccessPolicy()

    with pytest.raises(ValueError, match="non-empty"):
        policy.check("")

    with pytest.raises(ValueError, match="non-empty"):
        policy.allows("")


def test_name_access_policy_defensively_copies_sets() -> None:
    allowed = {"safe"}
    denied = {"blocked"}
    policy = NameAccessPolicy(
        allowed=allowed,
        denied=denied,
    )

    allowed.add("later")
    denied.add("safe")

    assert policy.allows("safe")
    assert not policy.allows("blocked")
    assert not policy.allows("later")


def test_name_access_policy_rejects_invalid_configured_names() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        NameAccessPolicy(
            allowed=frozenset({""}),
        )
