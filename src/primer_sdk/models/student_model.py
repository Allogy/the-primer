from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PreferenceSignal(BaseModel):
    id: UUID
    user_id: UUID
    org_id: UUID
    signal_type: str
    payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str


class MembershipEvent(BaseModel):
    user_id: UUID
    cohort_id: UUID
    action: str
    timestamp: datetime


class CohortSnapshot(BaseModel):
    timestamp: datetime
    member_count: int
    aggregate_state: dict[str, Any]
    drift_score: float


class Cohort(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    description: str
    strategy_type: str
    member_ids: set[UUID] = Field(default_factory=set)
    membership_history: list[MembershipEvent] = Field(default_factory=list)
    aggregate_state: dict[str, Any] = Field(default_factory=dict)
    state_version: int
    last_evolved: datetime
    snapshots: list[CohortSnapshot] = Field(default_factory=list)


class IngestResult(BaseModel):
    processed: int
    skipped: int
    failed: int
    errors: list[str] = Field(default_factory=list)


class MemoryEntry(BaseModel):
    """A single memory entry in any tier."""

    id: UUID
    tier: str  # 'short_term', 'long_term', 'working'
    dimension: str  # 'history', 'affinities', 'aspirations', 'regula'
    content: dict[str, Any]
    relevance_score: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None  # None = no expiry (long-term)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkingMemoryAssembly(BaseModel):
    """Assembled working memory for a learner — combines short-term + relevant long-term."""

    learner_id: UUID
    entries: list[MemoryEntry]
    assembled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    context_summary: str | None = None  # LLM-generated summary of the assembled context
