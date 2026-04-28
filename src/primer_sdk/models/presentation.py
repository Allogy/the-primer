from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChannelSession(BaseModel):
    id: UUID
    channel_type: str
    channel_user_id: str
    channel_conversation_id: str
    platform_user_id: UUID | None = None
    org_id: UUID | None = None
    workflow_run_id: UUID | None = None
    thread_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelMessage(BaseModel):
    id: str
    message_type: str  # 'text_input', 'hitl_decision', 'file_upload', 'command'
    content: str | dict[str, Any]
    session: ChannelSession
    raw_payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChannelFile(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    content: bytes
    source_url: str | None = None


class HitlGateConfig(BaseModel):
    node_id: str
    instructions: str | None = None
    context: dict[str, Any] | None = None
    options: list[str] = Field(default_factory=lambda: ["approve", "reject", "revise"])
    allow_comment: bool = True
    prompt: str | None = None
    input_type: str = "text"
    input_schema: dict[str, Any] | None = None
    placeholder: str | None = None
