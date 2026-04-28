from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class AGUIEventType(str, Enum):
    RUN_STARTED = "RUN_STARTED"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"
    TEXT_MESSAGE_START = "TEXT_MESSAGE_START"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    TEXT_MESSAGE_END = "TEXT_MESSAGE_END"
    STATE_SNAPSHOT = "STATE_SNAPSHOT"
    STATE_DELTA = "STATE_DELTA"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGS = "TOOL_CALL_ARGS"
    TOOL_CALL_END = "TOOL_CALL_END"
    TOOL_CALL_RESULT = "TOOL_CALL_RESULT"


class AGUIEvent(BaseModel):
    event_type: AGUIEventType
    thread_id: str
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = Field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.event_type.value,
            "thread_id": self.thread_id,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
        }


class RunStartedEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.RUN_STARTED


class RunFinishedEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.RUN_FINISHED


class RunErrorEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.RUN_ERROR
    error: str
    code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "error": self.error, "code": self.code}


class TextMessageStartEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.TEXT_MESSAGE_START
    message_id: str
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "message_id": self.message_id, "role": self.role}


class TextMessageContentEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.TEXT_MESSAGE_CONTENT
    message_id: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "message_id": self.message_id, "content": self.content}


class TextMessageEndEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.TEXT_MESSAGE_END
    message_id: str

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "message_id": self.message_id}


class StateSnapshotEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.STATE_SNAPSHOT
    state: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "state": self.state}


class StateDeltaEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.STATE_DELTA
    delta: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "delta": self.delta}


class ToolCallStartEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.TOOL_CALL_START
    tool_call_id: str
    tool_name: str

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "tool_call_id": self.tool_call_id, "tool_name": self.tool_name}


class ToolCallArgsEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.TOOL_CALL_ARGS
    tool_call_id: str
    args_chunk: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "tool_call_id": self.tool_call_id,
            "args_chunk": self.args_chunk,
        }


class ToolCallEndEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.TOOL_CALL_END
    tool_call_id: str

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "tool_call_id": self.tool_call_id}


class ToolCallResultEvent(AGUIEvent):
    event_type: AGUIEventType = AGUIEventType.TOOL_CALL_RESULT
    tool_call_id: str
    result: str

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "tool_call_id": self.tool_call_id, "result": self.result}
