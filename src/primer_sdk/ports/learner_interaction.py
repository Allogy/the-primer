"""Learner Interaction ports — Knowledge Graph, Learner Progress, and Teaching."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from primer_sdk.models.learner_interaction import (
    KnowledgeConcept,
    KnowledgeGraph,
    LearnerProgress,
    TeachingContext,
)


class KnowledgeGraphPort(ABC):
    """Query and manage Knowledge Graphs."""

    @abstractmethod
    async def get_graph(self, graph_id: UUID) -> KnowledgeGraph: ...

    @abstractmethod
    async def get_concept(self, concept_id: str) -> KnowledgeConcept: ...

    @abstractmethod
    async def get_prerequisites(self, concept_id: str) -> list[KnowledgeConcept]: ...

    @abstractmethod
    async def search_concepts(
        self, query: str, graph_id: UUID | None = None
    ) -> list[KnowledgeConcept]: ...


class LearnerProgressPort(ABC):
    """Track learner progress through Knowledge Graphs."""

    @abstractmethod
    async def get_progress(self, learner_id: UUID, graph_id: UUID) -> LearnerProgress: ...

    @abstractmethod
    async def update_mastery(self, learner_id: UUID, concept_id: str, score: float) -> None: ...

    @abstractmethod
    async def get_next_concept(
        self, learner_id: UUID, graph_id: UUID
    ) -> KnowledgeConcept | None: ...


class TeachingPort(ABC):
    """Assemble teaching context and manage teaching sessions."""

    @abstractmethod
    async def build_context(self, learner_id: UUID, concept_id: str) -> TeachingContext: ...

    @abstractmethod
    async def record_outcome(
        self, learner_id: UUID, concept_id: str, outcome: dict[str, Any]
    ) -> None: ...
