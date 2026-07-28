from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

from capillary_actions_sdk.events import AGUIEvent
from capillary_actions_sdk.models.student_model import MemoryEntry
from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)
from capillary_actions_sdk.schema.domain_schema import (
    DimensionSpec,
    DomainSchema,
    KnowledgeBaseWiring,
)

from primer_core.adapters.capillary.file_memory_store import FileMemoryStore
from primer_core.memory.core import MemoryCore
from primer_core.orchestrator.engagement import EngagementOrchestrator
from primer_core.orchestrator.hooks import HookContext, HookEvent, HookRegistry
from primer_core.orchestrator.writeback import on_struggle, write_back_outcome
from tests.domains.fakes import WritebackRunner, _skills


class OnStruggleRunner(RunWorkflowPort):
    """Return an engagement outcome containing schema-aligned on-struggle data."""

    def __init__(self) -> None:
        self.requests: list[RunWorkflowRequest] = []

    async def run(
        self,
        request: RunWorkflowRequest,
    ) -> AsyncIterator[AGUIEvent]:
        raise AssertionError("This integration test should use run_engagement, not streaming")
        yield  # pragma: no cover

    async def run_sync(
        self,
        request: RunWorkflowRequest,
    ) -> RunWorkflowResponse:
        self.requests.append(request)

        return RunWorkflowResponse(
            run_id="run-123",
            status="completed",
            output={"struggling": True},
        )


# Helper functions
def _schema(
    test_domain: str = "education", test_engagements: list[str] | None = None
) -> DomainSchema:
    return DomainSchema(
        domain=test_domain,
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
        engagements=test_engagements if test_engagements is not None else ["tutor-concept"],
    )


async def test_struggling_subject_adapted_to_easier_skill(tmp_path: Path) -> None:
    """
    BDD Scenario #2
    ---------------
    Scenario: a struggling subject is adapted to an easier skill

    Given on_struggle registered on ON_STRUGGLE_DETECTED
    And a subject whose payload marks them as struggling
    When the loop runs
    Then the next engagement selected comes from payload['next_skill']
    And the chosen skill was derived from the schema — zero domain vocabulary in the engine
    """
    recorded_payloads: list[dict] = []

    test_schema = _schema(
        test_domain="education",
        test_engagements=["foundational", "tutor-concept"],
    )
    test_skill_registry = _skills()

    test_subject_id = uuid4()
    test_memory = MemoryCore(schema=test_schema, store=FileMemoryStore(path=tmp_path / "mem.json"))

    test_hooks = HookRegistry()
    # Given on_struggle registered on ON_STRUGGLE_DETECTED
    test_hooks.register(event=HookEvent.ON_STRUGGLE_DETECTED, fn=on_struggle)

    async def record_payloads_after(context: HookContext) -> None:
        recorded_payloads.append(context.payload)

    test_hooks.register(event=HookEvent.AFTER_ENGAGEMENT, fn=record_payloads_after)

    # And a subject whose payload marks them as struggling
    test_orchestrator = EngagementOrchestrator(
        schema=test_schema,
        runner=OnStruggleRunner(),
        memory=test_memory,
        skills=test_skill_registry,
        hooks=test_hooks,
    )

    # When the loop runs
    await test_orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=test_subject_id,
        thread_id="thread-1",
    )

    # Then the next engagement selected comes from payload['next_skill']
    next_skill = recorded_payloads[0]["next_skill"]
    await test_orchestrator.run_engagement(
        skill_name=next_skill, subject_id=test_subject_id, thread_id="thread-2"
    )

    assert test_skill_registry.workflow_id("foundational") in [
        request.workflow_id for request in test_orchestrator.runner.requests
    ]


async def test_persistence_survives_with_entries_from_both_write_paths(tmp_path: Path) -> None:
    """
    BDD Scenario #3
    ---------------
    Scenario: persistence survives with entries from BOTH write paths

    Given session 1 wrote an outcome via the hook AND a direct MemoryCore.write entry
    When session 2 assembles working memory over the same file
    Then both entries are present with content, relevance_score, and metadata intact
    """
    test_schema = _schema()
    test_skill_registry = _skills()

    first_memory = MemoryCore(schema=test_schema, store=FileMemoryStore(path=tmp_path / "mem.json"))

    test_subject_id = uuid4()

    # Given session 1 wrote an outcome via the hook...
    test_hooks = HookRegistry()
    test_hooks.register(event=HookEvent.AFTER_ENGAGEMENT, fn=write_back_outcome)

    first_orchestrator = EngagementOrchestrator(
        schema=test_schema,
        runner=WritebackRunner(),
        memory=first_memory,
        skills=test_skill_registry,
        hooks=test_hooks,
    )

    await first_orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=test_subject_id,
        thread_id="thread-1",
    )

    write_back_signal_id = (await first_memory.store.get(subject_id=test_subject_id))[0].metadata[
        "signal_id"
    ]

    # ...AND a direct MemoryCore.write entry
    direct_signal_id = uuid4()
    test_entry = MemoryEntry(
        id=uuid4(),
        tier="long_term",
        dimension="history",
        content={"courses": ["calc-1"]},
        relevance_score=0.8,  # <-- Note change in relevance_score for direct MemoryCore.write entry
        metadata={
            "signal_id": direct_signal_id,
            "source": "primer_core.tests.integration.test_midpoint_feedback_loop",
        },
    )
    await first_memory.write(subject_id=test_subject_id, entry=test_entry)

    # When session 2 assembles working memory over the same file
    second_memory = MemoryCore(
        schema=test_schema, store=FileMemoryStore(path=tmp_path / "mem.json")
    )

    second_orchestrator = EngagementOrchestrator(
        schema=test_schema,
        runner=WritebackRunner(),
        memory=second_memory,
        skills=_skills(),
        # Lacks hooks -> Nothing new written to memory
    )
    await second_orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=test_subject_id,
        thread_id="thread-2",
    )
    session_2_working_memory_entries = (
        await second_orchestrator.memory.assemble_working_memory(subject_id=test_subject_id)
    ).entries

    # Then both entries are present with content, relevance_score, and metadata intact
    session_1_memory_entries = await first_memory.store.get(subject_id=test_subject_id)

    assert len(session_2_working_memory_entries) == len(session_1_memory_entries) == 2
    assert all(
        working_memory_entry in session_1_memory_entries
        for working_memory_entry in session_2_working_memory_entries
    )

    calc_entry = [
        entry for entry in session_2_working_memory_entries if "calc-1" in entry.content["courses"]
    ][0]
    physics_entry = [
        entry
        for entry in session_2_working_memory_entries
        if "physics-1" in entry.content["courses"]
    ][0]

    assert calc_entry.content == {"courses": ["calc-1"]}
    assert physics_entry.content == {"courses": ["physics-1"]}

    assert calc_entry.relevance_score == 0.8
    assert physics_entry.relevance_score == 1.0

    assert calc_entry.metadata == {
        "signal_id": str(direct_signal_id),
        "source": "primer_core.tests.integration.test_midpoint_feedback_loop",
    }
    assert physics_entry.metadata == {
        "signal_id": write_back_signal_id,
        "source": "primer_core.orchestrator",
    }
