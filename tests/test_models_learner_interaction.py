from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from primer_sdk.models.learner_interaction import (
    KnowledgeConcept,
    KnowledgeGraph,
    LearnerProgress,
    TeachingContext,
)


class TestKnowledgeConcept:
    def test_minimal_creation(self):
        concept = KnowledgeConcept(
            id="algebra-basics",
            name="Algebra Basics",
            description="Introduction to algebraic thinking",
        )
        assert concept.id == "algebra-basics"
        assert concept.name == "Algebra Basics"
        assert concept.prerequisites == []
        assert concept.difficulty == 1
        assert concept.tags == []
        assert concept.metadata == {}

    def test_with_all_fields(self):
        concept = KnowledgeConcept(
            id="quadratic-equations",
            name="Quadratic Equations",
            description="Solving equations of degree 2",
            prerequisites=["algebra-basics", "factoring"],
            difficulty=3,
            tags=["algebra", "equations"],
            metadata={"grade_level": "9"},
        )
        assert concept.difficulty == 3
        assert concept.prerequisites == ["algebra-basics", "factoring"]
        assert "algebra" in concept.tags

    def test_mutable_defaults_independent(self):
        c1 = KnowledgeConcept(id="a", name="A", description="A concept")
        c2 = KnowledgeConcept(id="b", name="B", description="B concept")
        c1.tags.append("math")
        assert c2.tags == []

    def test_difficulty_defaults_to_one(self):
        concept = KnowledgeConcept(id="intro", name="Intro", description="Introduction")
        assert concept.difficulty == 1


class TestKnowledgeGraph:
    def _make_concept(self, slug: str) -> KnowledgeConcept:
        return KnowledgeConcept(id=slug, name=slug.title(), description=f"Concept {slug}")

    def test_basic_creation(self):
        concepts = [self._make_concept("intro"), self._make_concept("advanced")]
        graph = KnowledgeGraph(
            id=uuid4(),
            name="Algebra I",
            description="First-year algebra curriculum",
            source="MIT OCW",
            concepts=concepts,
        )
        assert graph.name == "Algebra I"
        assert graph.source == "MIT OCW"
        assert len(graph.concepts) == 2
        assert graph.metadata == {}

    def test_id_is_uuid(self):
        graph = KnowledgeGraph(
            id=uuid4(),
            name="Physics",
            description="Physics curriculum",
            source="NGSS",
            concepts=[],
        )
        assert isinstance(graph.id, UUID)

    def test_empty_concepts_list(self):
        graph = KnowledgeGraph(
            id=uuid4(),
            name="Empty",
            description="Empty graph",
            source="internal",
            concepts=[],
        )
        assert graph.concepts == []

    def test_metadata_mutable_default_independent(self):
        g1 = KnowledgeGraph(id=uuid4(), name="G1", description="d", source="s", concepts=[])
        g2 = KnowledgeGraph(id=uuid4(), name="G2", description="d", source="s", concepts=[])
        g1.metadata["key"] = "val"
        assert g2.metadata == {}


class TestLearnerProgress:
    def test_minimal_creation(self):
        progress = LearnerProgress(
            learner_id=uuid4(),
            knowledge_graph_id=uuid4(),
        )
        assert progress.mastery == {}
        assert progress.current_concept is None
        assert progress.completed_concepts == []
        assert isinstance(progress.last_active, datetime)

    def test_with_mastery_data(self):
        progress = LearnerProgress(
            learner_id=uuid4(),
            knowledge_graph_id=uuid4(),
            mastery={"intro": 0.9, "factoring": 0.6},
            current_concept="quadratic",
            completed_concepts=["intro", "factoring"],
        )
        assert progress.mastery["intro"] == 0.9
        assert progress.current_concept == "quadratic"
        assert len(progress.completed_concepts) == 2

    def test_ids_are_uuids(self):
        learner_id = uuid4()
        graph_id = uuid4()
        progress = LearnerProgress(learner_id=learner_id, knowledge_graph_id=graph_id)
        assert isinstance(progress.learner_id, UUID)
        assert isinstance(progress.knowledge_graph_id, UUID)

    def test_last_active_defaults_to_utcnow(self):
        before = datetime.now(tz=timezone.utc)
        progress = LearnerProgress(learner_id=uuid4(), knowledge_graph_id=uuid4())
        after = datetime.now(tz=timezone.utc)
        assert before <= progress.last_active <= after

    def test_mutable_defaults_independent(self):
        p1 = LearnerProgress(learner_id=uuid4(), knowledge_graph_id=uuid4())
        p2 = LearnerProgress(learner_id=uuid4(), knowledge_graph_id=uuid4())
        p1.completed_concepts.append("intro")
        assert p2.completed_concepts == []


class TestTeachingContext:
    def _make_progress(self) -> LearnerProgress:
        return LearnerProgress(learner_id=uuid4(), knowledge_graph_id=uuid4())

    def _make_concept(self) -> KnowledgeConcept:
        return KnowledgeConcept(
            id="quadratic",
            name="Quadratic Equations",
            description="Solving quadratic equations",
            difficulty=3,
        )

    def test_minimal_creation(self):
        ctx = TeachingContext(
            learner_progress=self._make_progress(),
            target_concept=self._make_concept(),
        )
        assert ctx.student_working_memory == {}
        assert ctx.recommended_approach is None

    def test_with_all_fields(self):
        ctx = TeachingContext(
            learner_progress=self._make_progress(),
            target_concept=self._make_concept(),
            student_working_memory={"recent_errors": ["sign_error"]},
            recommended_approach="worked_example",
        )
        assert ctx.recommended_approach == "worked_example"
        assert ctx.student_working_memory == {"recent_errors": ["sign_error"]}

    def test_nested_model_access(self):
        progress = self._make_progress()
        concept = self._make_concept()
        ctx = TeachingContext(learner_progress=progress, target_concept=concept)
        assert ctx.target_concept.id == "quadratic"
        assert ctx.target_concept.difficulty == 3
        assert isinstance(ctx.learner_progress.learner_id, UUID)

    def test_mutable_defaults_independent(self):
        ctx1 = TeachingContext(
            learner_progress=self._make_progress(), target_concept=self._make_concept()
        )
        ctx2 = TeachingContext(
            learner_progress=self._make_progress(), target_concept=self._make_concept()
        )
        ctx1.student_working_memory["key"] = "val"
        assert ctx2.student_working_memory == {}
