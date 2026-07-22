"""Tests for local trigger evaluation."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

import pytest
from capillary_actions_sdk.models.learning_actions import (
    TriggerDefinition,
    TriggerTarget,
)

from primer_core.orchestrator.triggers import TriggerScheduler


def _trigger(
    *,
    trigger_type: str = "conditional",
    config: dict[str, Any] | None = None,
    enabled: bool = True,
) -> TriggerDefinition:
    """Construct a trigger for isolated scheduler tests."""
    return TriggerDefinition.model_construct(
        id=uuid4(),
        org_id=uuid4(),
        name="test-trigger",
        trigger_type=trigger_type,
        config={} if config is None else config,
        target=cast(TriggerTarget, object()),
        enabled=enabled,
        created_at=datetime.now(UTC),
        last_fired=None,
        fire_count=0,
    )


@pytest.mark.parametrize(
    ("mastery_score", "expected"),
    [
        (0.5, ["review-spaced"]),
        (0.9, []),
    ],
)
def test_conditional_trigger_fires_only_when_predicate_matches(
    mastery_score: float,
    expected: list[str],
) -> None:
    trigger = _trigger(
        config={
            "engagement": "review-spaced",
            "field": "mastery_score",
            "operator": "<",
            "value": 0.7,
        }
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(
        payload={"mastery_score": mastery_score},
    )

    assert result == expected


def test_disabled_trigger_never_fires() -> None:
    trigger = _trigger(
        enabled=False,
        config={
            "engagement": "review-spaced",
            "field": "mastery_score",
            "operator": "<",
            "value": 0.7,
        },
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(
        payload={"mastery_score": 0.5},
    )

    assert result == []


@pytest.mark.parametrize(
    ("operator_name", "actual", "expected", "should_fire"),
    [
        ("<", 1, 2, True),
        ("<=", 2, 2, True),
        (">", 3, 2, True),
        (">=", 2, 2, True),
        ("==", "ready", "ready", True),
        ("!=", "ready", "blocked", True),
        ("<", 3, 2, False),
        ("==", "ready", "blocked", False),
    ],
)
def test_conditional_trigger_supports_configured_operators(
    operator_name: str,
    actual: Any,
    expected: Any,
    should_fire: bool,
) -> None:
    trigger = _trigger(
        config={
            "engagement": "next-engagement",
            "field": "metric",
            "operator": operator_name,
            "value": expected,
        }
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(payload={"metric": actual})

    if should_fire:
        assert result == ["next-engagement"]
    else:
        assert result == []


def test_conditional_trigger_does_not_fire_when_field_is_missing() -> None:
    trigger = _trigger(
        config={
            "engagement": "next-engagement",
            "field": "score",
            "operator": "<",
            "value": 0.7,
        }
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(payload={})

    assert result == []


def test_conditional_trigger_does_not_fire_for_unknown_operator() -> None:
    trigger = _trigger(
        config={
            "engagement": "next-engagement",
            "field": "score",
            "operator": "approximately",
            "value": 0.7,
        }
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(payload={"score": 0.5})

    assert result == []


def test_conditional_trigger_does_not_fire_for_incompatible_values() -> None:
    trigger = _trigger(
        config={
            "engagement": "next-engagement",
            "field": "score",
            "operator": "<",
            "value": 0.7,
        }
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(payload={"score": "low"})

    assert result == []


def test_unknown_trigger_type_does_not_fire() -> None:
    trigger = _trigger(
        trigger_type="unsupported",
        config={
            "engagement": "next-engagement",
        },
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(payload={})

    assert result == []


def test_matching_trigger_without_string_engagement_is_ignored() -> None:
    trigger = _trigger(
        config={
            "engagement": None,
            "field": "score",
            "operator": "<",
            "value": 0.7,
        }
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(payload={"score": 0.5})

    assert result == []


def test_multiple_matching_triggers_preserve_definition_order() -> None:
    first = _trigger(
        config={
            "engagement": "first-engagement",
            "field": "score",
            "operator": "<",
            "value": 0.7,
        }
    )
    second = _trigger(
        config={
            "engagement": "second-engagement",
            "field": "score",
            "operator": "<=",
            "value": 0.5,
        }
    )
    scheduler = TriggerScheduler([first, second])

    result = scheduler.evaluate(payload={"score": 0.5})

    assert result == [
        "first-engagement",
        "second-engagement",
    ]


def test_cron_trigger_fires_when_supplied_time_matches() -> None:
    trigger = _trigger(
        trigger_type="cron",
        config={
            "engagement": "scheduled-review",
            "minute": 30,
            "hour": 14,
            "weekday": 2,
        },
    )
    scheduler = TriggerScheduler([trigger])
    now = datetime(2026, 7, 22, 14, 30, tzinfo=UTC)

    result = scheduler.evaluate(
        payload={},
        now=now,
    )

    assert result == ["scheduled-review"]


def test_cron_trigger_does_not_fire_when_supplied_time_differs() -> None:
    trigger = _trigger(
        trigger_type="cron",
        config={
            "engagement": "scheduled-review",
            "minute": 30,
            "hour": 14,
        },
    )
    scheduler = TriggerScheduler([trigger])
    now = datetime(2026, 7, 22, 15, 30, tzinfo=UTC)

    result = scheduler.evaluate(
        payload={},
        now=now,
    )

    assert result == []


def test_cron_trigger_requires_supplied_time() -> None:
    trigger = _trigger(
        trigger_type="cron",
        config={
            "engagement": "scheduled-review",
            "hour": 14,
        },
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(payload={})

    assert result == []


def test_cron_trigger_supports_wildcards_and_multiple_values() -> None:
    trigger = _trigger(
        trigger_type="cron",
        config={
            "engagement": "scheduled-review",
            "minute": "*",
            "hour": [9, 14, 18],
            "weekday": {0, 2, 4},
        },
    )
    scheduler = TriggerScheduler([trigger])
    now = datetime(2026, 7, 22, 14, 47, tzinfo=UTC)

    result = scheduler.evaluate(
        payload={},
        now=now,
    )

    assert result == ["scheduled-review"]


def test_cron_trigger_requires_at_least_one_time_constraint() -> None:
    trigger = _trigger(
        trigger_type="cron",
        config={
            "engagement": "scheduled-review",
        },
    )
    scheduler = TriggerScheduler([trigger])

    result = scheduler.evaluate(
        payload={},
        now=datetime(2026, 7, 22, 14, 30, tzinfo=UTC),
    )

    assert result == []
