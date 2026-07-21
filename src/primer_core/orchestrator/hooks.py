"""Domain-agnostic engagement hooks."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from capillary_actions_sdk.schema import DomainSchema

    from primer_core.memory import MemoryCore


class HookEvent(StrEnum):
    BEFORE_ENGAGEMENT = "before_engagement"
    AFTER_ENGAGEMENT = "after_engagement"
    ON_MASTERY_CHANGE = "on_mastery_change"
    ON_STRUGGLE_DETECTED = "on_struggle_detected"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"


class HookContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    subject_id: UUID
    schema: DomainSchema
    engagement: str
    payload: dict[str, Any] = Field(default_factory=dict)
    memory: MemoryCore


HookHandler = Callable[[HookContext], Awaitable[None]]


class HookRegistry:
    def __init__(self) -> None:
        self._handlers: dict[HookEvent, list[HookHandler]] = defaultdict(list)

    def register(self, event: HookEvent, fn: HookHandler) -> None:
        self._handlers[event].append(fn)

    async def fire(self, event: HookEvent, ctx: HookContext) -> None:
        for handler in self._handlers.get(event, []):
            await handler(ctx)
