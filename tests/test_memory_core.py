from __future__ import annotations

from uuid import uuid4

import pytest
from capillary_actions_sdk.models.student_model import (
    MemoryEntry,
    PreferenceSignal,
)
from capillary_actions_sdk.reference.in_memory_memory_store import InMemoryMemoryStore
from capillary_actions_sdk.schema.domain_schema import (
    DimensionSpec,
    DomainSchema,
    KnowledgeBaseWiring,
)

from primer_core.memory.core import MemoryCore


class TestMemoryCoreWrite:
    async def test_write_persists_caller_built_schema_valid_entry(self):
        """
        BDD Scenario #1
        ---------------
        Scenario: write persists a caller-built, schema-valid entry

        Given a MemoryCore built from an education DomainSchema and an InMemoryMemoryStore
        And a MemoryEntry in the declared dimension "history" with declared content fields
        When I call write(subject_id, entry)
        Then the same entry is returned
        And store.get(subject_id) returns exactly that one entry
        """
        test_schema = DomainSchema(
            domain="education",
            subject="learner",
            dimensions=[DimensionSpec(name="history", fields=["courses_completed"])],
            knowledge_base=KnowledgeBaseWiring(kb_names=["primer-education-kb"]),
            engagements=["tutor-concept"],
        )
        test_store = InMemoryMemoryStore()

        test_subject_id = uuid4()

        test_core = MemoryCore(schema=test_schema, store=test_store)

        test_entry = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension="history",
            content={
                "courses_completed": ["APUSH"],
            },
        )

        result_entry = await test_core.write(subject_id=test_subject_id, entry=test_entry)

        assert test_entry == result_entry
        assert await test_store.get(test_subject_id) == [test_entry]


class TestMemoryCoreIngest:
    async def test_ingest_maps_PreferenceSignal_to_schema_validated_MemoryEntry(self):
        """
        BDD Scenario #2
        ---------------
        Scenario: ingest maps a PreferenceSignal to a schema-validated MemoryEntry

        Given a MemoryCore over the education schema
        And a PreferenceSignal whose payload has dimension="history"
            and content={"courses_completed": ["calc-1"]}
        When I call ingest(subject_id, signal)
        Then a MemoryEntry is returned with dimension "history",
            tier "long_term", and the same content
        And the entry is persisted to the store
        """
        test_schema = DomainSchema(
            domain="education",
            subject="learner",
            dimensions=[DimensionSpec(name="history", fields=["courses_completed"])],
            knowledge_base=KnowledgeBaseWiring(kb_names=["primer-education-kb"]),
            engagements=["tutor-concept"],
        )
        test_store = InMemoryMemoryStore()

        test_subject_id = uuid4()

        test_preference_signal = PreferenceSignal(
            id=uuid4(),
            user_id=test_subject_id,
            org_id=uuid4(),
            signal_type="short_term",
            payload={"dimension": "history", "content": {"courses_completed": ["calc-1"]}},
            source="test",
        )

        test_core = MemoryCore(schema=test_schema, store=test_store)

        result_entry = await test_core.ingest(
            subject_id=test_subject_id, signal=test_preference_signal
        )

        assert result_entry.dimension == "history"
        assert result_entry.tier == "long_term"
        assert result_entry.content == {"courses_completed": ["calc-1"]}
        assert await test_store.get(subject_id=test_subject_id) == [result_entry]

    async def test_write_ingest_rejects_undeclared_dimension(self):
        """
        BDD Scenario #3
        ---------------
        Scenario: write/ingest rejects an undeclared dimension

        Given a MemoryCore over the education schema (no "risk_appetite" dimension)
        When I ingest a signal with dimension "risk_appetite"
        Then a ValueError is raised mentioning dimension 'risk_appetite'
        """
        test_schema = DomainSchema(
            domain="education",
            subject="learner",
            dimensions=[DimensionSpec(name="history", fields=["courses_completed"])],
            knowledge_base=KnowledgeBaseWiring(kb_names=["primer-education-kb"]),
            engagements=["tutor-concept"],
        )
        test_store = InMemoryMemoryStore()

        test_subject_id = uuid4()

        test_core = MemoryCore(schema=test_schema, store=test_store)

        test_preference_signal = PreferenceSignal(
            id=uuid4(),
            user_id=test_subject_id,
            org_id=uuid4(),
            signal_type="short_term",
            payload={"dimension": "risk_appetite", "content": {"courses_completed": ["calc-1"]}},
            source="test",
        )

        with pytest.raises(ValueError, match="risk_appetite"):
            await test_core.ingest(subject_id=test_subject_id, signal=test_preference_signal)

    async def test_write_ingest_rejects_undeclared_content_field(self):
        """
        BDD Scenario #4
        ---------------
        Scenario: write/ingest rejects an undeclared content field (G2, engine-side)

        Given a MemoryCore over the education schema where
            "history" declares fields ["courses_completed", "exercises"]
        When I ingest a signal with dimension "history" and content {"unknown_field": 1}
        Then a ValueError is raised whose message includes "unknown_field"
        """
        test_schema = DomainSchema(
            domain="education",
            subject="learner",
            dimensions=[DimensionSpec(name="history", fields=["courses_completed", "exercises"])],
            knowledge_base=KnowledgeBaseWiring(kb_names=["primer-education-kb"]),
            engagements=["tutor-concept"],
        )
        test_store = InMemoryMemoryStore()

        test_subject_id = uuid4()

        test_preference_signal = PreferenceSignal(
            id=uuid4(),
            user_id=test_subject_id,
            org_id=uuid4(),
            signal_type="short_term",
            payload={"dimension": "history", "content": {"unknown_field": 1}},
            source="test",
        )

        test_core = MemoryCore(schema=test_schema, store=test_store)

        with pytest.raises(ValueError, match="unknown_field"):
            await test_core.ingest(subject_id=test_subject_id, signal=test_preference_signal)

    async def test_ingest_without_a_dimension_key_fails_loudly(self):
        """
        BDD Scenario #5
        ---------------
        Scenario: ingest without a dimension key fails loudly

        Given a PreferenceSignal whose payload has no "dimension" key
        When I ingest it
        Then a KeyError is raised
        """
        test_schema = DomainSchema(
            domain="education",
            subject="learner",
            dimensions=[DimensionSpec(name="history", fields=["courses_completed"])],
            knowledge_base=KnowledgeBaseWiring(kb_names=["primer-education-kb"]),
            engagements=["tutor-concept"],
        )
        test_store = InMemoryMemoryStore()

        test_subject_id = uuid4()

        test_preference_signal = PreferenceSignal(
            id=uuid4(),
            user_id=test_subject_id,
            org_id=uuid4(),
            signal_type="short_term",
            payload={"content": {"courses_completed": ["calc-1"]}},
            source="test",
        )

        test_core = MemoryCore(schema=test_schema, store=test_store)

        with pytest.raises(KeyError):
            await test_core.ingest(subject_id=test_subject_id, signal=test_preference_signal)


class TestMemoryCoreAssemble:
    async def test_assemble_working_memory_returns_all_entries_for_subject(self):
        """
        BDD Scenario #6
        ---------------
        Scenario: assemble_working_memory returns all entries for the subject

        Given two ingested signals for the same subject in different dimensions
        When I call assemble_working_memory(subject_id)
        Then a WorkingMemoryAssembly is returned with learner_id == subject_id
        And it contains exactly those two entries
        """
        test_schema = DomainSchema(
            domain="education",
            subject="learner",
            dimensions=[
                DimensionSpec(name="history", fields=["courses_completed"]),
                DimensionSpec(name="math", fields=["courses_completed"]),
            ],
            knowledge_base=KnowledgeBaseWiring(kb_names=["primer-education-kb"]),
            engagements=["tutor-concept"],
        )
        test_store = InMemoryMemoryStore()

        test_subject_id = uuid4()

        test_core = MemoryCore(schema=test_schema, store=test_store)

        test_preference_signal_1 = PreferenceSignal(
            id=uuid4(),
            user_id=test_subject_id,
            org_id=uuid4(),
            signal_type="short_term",
            payload={
                "dimension": "history",
                "content": {"courses_completed": ["APUSH", "modern-world-history"]},
            },
            source="test",
        )
        test_preference_signal_2 = PreferenceSignal(
            id=uuid4(),
            user_id=test_subject_id,
            org_id=uuid4(),
            signal_type="short_term",
            payload={
                "dimension": "math",
                "content": {"courses_completed": ["calc-1", "algebra-2"]},
            },
            source="test",
        )

        test_entry_1 = await test_core.ingest(
            subject_id=test_subject_id, signal=test_preference_signal_1
        )
        test_entry_2 = await test_core.ingest(
            subject_id=test_subject_id, signal=test_preference_signal_2
        )

        test_working_memory_assembly = await test_core.assemble_working_memory(
            subject_id=test_subject_id
        )

        assert test_working_memory_assembly.learner_id == test_subject_id
        assert test_entry_1 in test_working_memory_assembly.entries
        assert test_entry_2 in test_working_memory_assembly.entries

    async def test_assemble_working_memory_is_subject_scoped_empty_by_default(self):
        """
        BDD Scenario #7
        ---------------
        Scenario: assemble_working_memory is subject-scoped and empty by default

        Given an entry written for subject A
        When I assemble working memory for a different subject B
        Then the assembly entries list is empty
        """
        test_schema = DomainSchema(
            domain="education",
            subject="learner",
            dimensions=[DimensionSpec(name="history", fields=["courses_completed"])],
            knowledge_base=KnowledgeBaseWiring(kb_names=["primer-education-kb"]),
            engagements=["tutor-concept"],
        )
        test_store = InMemoryMemoryStore()

        test_subject_id_A = uuid4()
        test_subject_id_B = uuid4()

        test_core = MemoryCore(schema=test_schema, store=test_store)

        test_entry_A = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension="history",
            content={
                "courses_completed": ["APUSH"],
            },
        )

        await test_core.write(subject_id=test_subject_id_A, entry=test_entry_A)

        test_working_memory_assembly = await test_core.assemble_working_memory(
            subject_id=test_subject_id_B
        )

        assert len(test_working_memory_assembly.entries) == 0
