"""Tests for engagement outcome write-back handlers."""

from uuid import UUID, uuid4

import pytest
from capillary_actions_sdk.models.student_model import PreferenceSignal
from capillary_actions_sdk.schema import (
    DimensionSpec,
    DomainSchema,
    KnowledgeBaseWiring,
)

from primer_core.memory import MemoryCore
from primer_core.orchestrator.hooks import HookContext
from primer_core.orchestrator.writeback import (
    SENTINEL_ORG_ID,
    on_struggle,
    write_back_outcome,
)


class RecordingMemoryCore(MemoryCore):
    """Record asynchronous ingest calls without using a store."""

    def __init__(self) -> None:
        object.__setattr__(self, "ingest_calls", [])

    async def ingest(
        self,
        subject_id: UUID,
        signal: PreferenceSignal,
    ) -> None:
        self.ingest_calls.append((subject_id, signal))


def _schema() -> DomainSchema:
    return DomainSchema(
        domain="education",
        subject="learner",
        dimensions=[
            DimensionSpec(
                name="history",
                fields=["courses"],
            )
        ],
        knowledge_base=KnowledgeBaseWiring(
            kb_names=["primer-education-kb"],
        ),
        engagements=["tutor-concept"],
    )


async def test_write_back_outcome_ingests_preference_signal() -> None:
    subject_id = uuid4()
    memory = RecordingMemoryCore()

    context = HookContext(
        subject_id=subject_id,
        schema=_schema(),
        engagement="tutor-concept",
        payload={
            "outcome": {
                "answer": "Recursion calls itself.",
            },
            "writeback": {
                "dimension": "history",
                "content": {
                    "courses": ["recursion"],
                },
            },
        },
        memory=memory,
    )

    await write_back_outcome(context)

    assert len(memory.ingest_calls) == 1

    ingested_subject_id, signal = memory.ingest_calls[0]

    assert ingested_subject_id == subject_id
    assert isinstance(signal, PreferenceSignal)
    assert isinstance(signal.id, UUID)
    assert signal.user_id == subject_id
    assert signal.org_id == SENTINEL_ORG_ID
    assert signal.signal_type == "engagement_outcome"
    assert signal.payload == {
        "dimension": "history",
        "content": {
            "courses": ["recursion"],
        },
    }
    assert signal.source == "primer_core.orchestrator"


async def test_write_back_outcome_reads_mapping_from_outcome() -> None:
    subject_id = uuid4()
    org_id = uuid4()
    memory = RecordingMemoryCore()

    context = HookContext(
        subject_id=subject_id,
        schema=_schema(),
        engagement="tutor-concept",
        payload={
            "org_id": org_id,
            "outcome": {
                "answer": "Recursion calls itself.",
                "writeback": {
                    "dimension": "history",
                    "content": {
                        "courses": ["recursion"],
                    },
                },
            },
        },
        memory=memory,
    )

    await write_back_outcome(context)

    assert len(memory.ingest_calls) == 1

    ingested_subject_id, signal = memory.ingest_calls[0]

    assert ingested_subject_id == subject_id
    assert signal.user_id == subject_id
    assert signal.org_id == org_id
    assert signal.payload == {
        "dimension": "history",
        "content": {
            "courses": ["recursion"],
        },
    }


async def test_write_back_outcome_requires_mapping() -> None:
    context = HookContext(
        subject_id=uuid4(),
        schema=_schema(),
        engagement="tutor-concept",
        payload={
            "outcome": {
                "answer": "Recursion calls itself.",
            },
        },
        memory=RecordingMemoryCore(),
    )

    with pytest.raises(
        ValueError,
        match="Engagement outcome must contain a writeback mapping",
    ):
        await write_back_outcome(context)


async def test_on_struggle_selects_previous_schema_engagement() -> None:
    schema = DomainSchema(
        domain="test-domain",
        subject="test-subject",
        dimensions=[],
        knowledge_base=KnowledgeBaseWiring(kb_names=[]),
        engagements=[
            "foundational",
            "guided",
            "independent",
        ],
    )

    context = HookContext(
        subject_id=uuid4(),
        schema=schema,
        engagement="independent",
        payload={"struggling": True},
        memory=RecordingMemoryCore(),
    )

    await on_struggle(context)

    assert context.payload["next_skill"] == "guided"


async def test_on_struggle_does_nothing_when_not_struggling() -> None:
    schema = DomainSchema(
        domain="test-domain",
        subject="test-subject",
        dimensions=[],
        knowledge_base=KnowledgeBaseWiring(kb_names=[]),
        engagements=["foundational", "guided"],
    )

    context = HookContext(
        subject_id=uuid4(),
        schema=schema,
        engagement="guided",
        payload={"struggling": False},
        memory=RecordingMemoryCore(),
    )

    await on_struggle(context)

    assert "next_skill" not in context.payload


async def test_on_struggle_does_nothing_at_simplest_engagement() -> None:
    schema = DomainSchema(
        domain="test-domain",
        subject="test-subject",
        dimensions=[],
        knowledge_base=KnowledgeBaseWiring(kb_names=[]),
        engagements=["foundational", "guided"],
    )

    context = HookContext(
        subject_id=uuid4(),
        schema=schema,
        engagement="foundational",
        payload={"struggling": True},
        memory=RecordingMemoryCore(),
    )

    await on_struggle(context)

    assert "next_skill" not in context.payload
