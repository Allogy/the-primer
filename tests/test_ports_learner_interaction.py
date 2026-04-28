from __future__ import annotations

from uuid import uuid4

import pytest

from primer_sdk.ports.learner_interaction import (
    KnowledgeGraphPort,
    LearnerProgressPort,
    TeachingPort,
)

# ---------------------------------------------------------------------------
# ABC instantiation tests — none of these can be created directly
# ---------------------------------------------------------------------------


class TestKnowledgeGraphPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            KnowledgeGraphPort()  # type: ignore[abstract]


class TestLearnerProgressPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            LearnerProgressPort()  # type: ignore[abstract]


class TestTeachingPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            TeachingPort()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Concrete implementation tests
# ---------------------------------------------------------------------------


class ConcreteKnowledgeGraphPort(KnowledgeGraphPort):
    async def get_graph(self, graph_id):
        from primer_sdk.models.learner_interaction import KnowledgeGraph

        return KnowledgeGraph(
            id=graph_id,
            name="Test Graph",
            description="A test knowledge graph",
            source="test",
            concepts=[],
        )

    async def get_concept(self, concept_id):
        from primer_sdk.models.learner_interaction import KnowledgeConcept

        return KnowledgeConcept(id=concept_id, name=concept_id.title(), description="Test concept")

    async def get_prerequisites(self, concept_id):
        return []

    async def search_concepts(self, query, graph_id=None):
        return []


class TestConcreteKnowledgeGraphPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteKnowledgeGraphPort()
        assert isinstance(port, KnowledgeGraphPort)


class ConcreteLearnerProgressPort(LearnerProgressPort):
    async def get_progress(self, learner_id, graph_id):
        from primer_sdk.models.learner_interaction import LearnerProgress

        return LearnerProgress(learner_id=learner_id, knowledge_graph_id=graph_id)

    async def update_mastery(self, learner_id, concept_id, score):
        return None

    async def get_next_concept(self, learner_id, graph_id):
        return None


class TestConcreteLearnerProgressPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteLearnerProgressPort()
        assert isinstance(port, LearnerProgressPort)


class ConcreteTeachingPort(TeachingPort):
    async def build_context(self, learner_id, concept_id):
        from primer_sdk.models.learner_interaction import (
            KnowledgeConcept,
            LearnerProgress,
            TeachingContext,
        )

        progress = LearnerProgress(learner_id=learner_id, knowledge_graph_id=uuid4())
        concept = KnowledgeConcept(id=concept_id, name=concept_id.title(), description="Test")
        return TeachingContext(learner_progress=progress, target_concept=concept)

    async def record_outcome(self, learner_id, concept_id, outcome):
        return None


class TestConcreteTeachingPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteTeachingPort()
        assert isinstance(port, TeachingPort)
