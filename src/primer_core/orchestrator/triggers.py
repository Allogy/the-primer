"""Local evaluation of engagement trigger definitions."""

from __future__ import annotations

import operator
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any

from capillary_actions_sdk.models.learning_actions import TriggerDefinition

Comparator = Callable[[Any, Any], bool]

_COMPARATORS: dict[str, Comparator] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


class TriggerScheduler:
    """Evaluate trigger definitions without running a background scheduler."""

    def __init__(self, triggers: Sequence[TriggerDefinition]) -> None:
        self._triggers = list(triggers)

    def evaluate(
        self,
        payload: Mapping[str, Any],
        now: datetime | None = None,
    ) -> list[str]:
        """Return engagements belonging to enabled, matching triggers."""
        engagements: list[str] = []

        for trigger in self._triggers:
            if not trigger.enabled:
                continue

            if not self._matches(trigger, payload, now):
                continue

            engagement = trigger.config.get("engagement")

            if isinstance(engagement, str):
                engagements.append(engagement)

        return engagements

    def _matches(
        self,
        trigger: TriggerDefinition,
        payload: Mapping[str, Any],
        now: datetime | None,
    ) -> bool:
        if trigger.trigger_type == "conditional":
            return self._matches_conditional(trigger, payload)

        if trigger.trigger_type == "cron":
            return self._matches_cron(trigger, now)

        return False

    def _matches_conditional(
        self,
        trigger: TriggerDefinition,
        payload: Mapping[str, Any],
    ) -> bool:
        field = trigger.config.get("field")
        operator_name = trigger.config.get("operator")

        if not isinstance(field, str):
            return False

        if not isinstance(operator_name, str):
            return False

        if field not in payload or "value" not in trigger.config:
            return False

        comparator = _COMPARATORS.get(operator_name)

        if comparator is None:
            return False

        actual = payload[field]
        expected = trigger.config["value"]

        try:
            return comparator(actual, expected)
        except TypeError:
            return False

    def _matches_cron(
        self,
        trigger: TriggerDefinition,
        now: datetime | None,
    ) -> bool:
        if now is None:
            return False

        time_fields = {
            "minute": now.minute,
            "hour": now.hour,
            "day": now.day,
            "month": now.month,
            "weekday": now.weekday(),
        }

        has_time_constraint = False

        for name, actual in time_fields.items():
            if name not in trigger.config:
                continue

            has_time_constraint = True
            expected = trigger.config[name]

            if expected == "*":
                continue

            if isinstance(expected, int) and expected == actual:
                continue

            if isinstance(expected, (list, tuple, set)) and actual in expected:
                continue

            return False

        return has_time_constraint
