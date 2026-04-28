"""Learner Interaction models — Knowledge Graph, Learner Progress, and Teaching Context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeConcept(BaseModel):
    """A node in the Knowledge Graph representing a teachable concept."""

    id: str  # slug identifier
    name: str
    description: str
    prerequisites: list[str] = Field(default_factory=list)  # IDs of prerequisite concepts
    difficulty: int = 1  # 1-5 scale
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraph(BaseModel):
    """A structured representation of a course or curriculum."""

    id: UUID
    name: str
    description: str
    source: str  # e.g., 'MIT OCW', 'NGSS', 'XRP'
    concepts: list[KnowledgeConcept]
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearnerProgress(BaseModel):
    """Tracks a learner's progress through a Knowledge Graph."""

    learner_id: UUID
    knowledge_graph_id: UUID
    mastery: dict[str, float] = Field(default_factory=dict)  # concept_id -> mastery score (0-1)
    current_concept: str | None = None
    completed_concepts: list[str] = Field(default_factory=list)
    last_active: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TeachingContext(BaseModel):
    """Assembled context for a teaching interaction — combines KG + Student Model."""

    learner_progress: LearnerProgress
    target_concept: KnowledgeConcept
    student_working_memory: dict[str, Any] = Field(default_factory=dict)
    recommended_approach: str | None = None  # e.g., 'visual', 'worked_example', 'socratic'
