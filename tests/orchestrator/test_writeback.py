"""Tests for engagement outcome write-back handlers."""

from uuid import UUID, uuid4

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
    """Record ingest calls without using a real memory store."""

    def __init__(self) -> None:
        object.__setattr__(self, "ingest_calls", [])

    def ingest(
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
    outcome = {
        "answer": "Recursion calls itself.",
        "status": "completed",
    }

    context = HookContext(
        subject_id=subject_id,
        schema=_schema(),
        engagement="tutor-concept",
        payload={"outcome": outcome},
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
        "engagement": "tutor-concept",
        "outcome": outcome,
    }
    assert signal.source == "primer_core.orchestrator"


async def test_write_back_outcome_uses_payload_org_id() -> None:
    subject_id = uuid4()
    org_id = uuid4()
    memory = RecordingMemoryCore()

    context = HookContext(
        subject_id=subject_id,
        schema=_schema(),
        engagement="tutor-concept",
        payload={
            "org_id": org_id,
            "outcome": {"result": "success"},
        },
        memory=memory,
    )

    await write_back_outcome(context)

    assert len(memory.ingest_calls) == 1

    ingested_subject_id, signal = memory.ingest_calls[0]

    assert ingested_subject_id == subject_id
    assert signal.org_id == org_id
    assert signal.user_id == subject_id
    assert signal.payload["outcome"] == {"result": "success"}


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
