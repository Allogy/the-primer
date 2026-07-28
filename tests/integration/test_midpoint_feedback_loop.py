from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from capillary_actions_sdk.events import AGUIEvent
from capillary_actions_sdk.models.student_model import MemoryEntry, PreferenceSignal
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
from primer_core.orchestrator.engagement import EngagementOrchestrator
from primer_core.orchestrator.hooks import HookContext, HookEvent, HookRegistry
from primer_core.orchestrator.writeback import on_struggle, write_back_outcome

from primer_core.adapters.capillary.file_memory_store import FileMemoryStore
from primer_core.memory.core import MemoryCore
from primer_core.skills import SkillRegistry


class WritebackRunner(RunWorkflowPort):
    """Return an engagement outcome containing schema-aligned write-back data."""

    def __init__(self) -> None:
        self.requests: list[RunWorkflowRequest] = []

    async def run_sync(
        self,
        request: RunWorkflowRequest,
    ) -> RunWorkflowResponse:
        self.requests.append(request)

        return RunWorkflowResponse(
            run_id="run-123",
            status="completed",
            output={
                "answer": "Gravity is 9.8 m/s/s.",
                "writeback": {
                    "dimension": "history",
                    "content": {
                        "courses": ["physics-1"],
                    },
                },
            },
        )

    async def run(
        self,
        request: RunWorkflowRequest,
    ) -> AsyncIterator[AGUIEvent]:
        raise AssertionError("This integration test should use run_engagement, not streaming")
        yield  # pragma: no cover


class OnStruggleRunner(RunWorkflowPort):
    """Return an engagement outcome containing schema-aligned on-struggle data."""

    def __init__(self) -> None:
        self.requests: list[RunWorkflowRequest] = []

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


# Helper functions
def _schema(
    test_domain: str = "education", test_engagements: list[str] = ["tutor-concept"]
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
        engagements=test_engagements,
    )


def _skills() -> SkillRegistry:
    skills = SkillRegistry()
    skills.register(
        "tutor-concept",
        "src/primer_core/wdfs/tutor-concept.yaml",
    )
    return skills


async def test_session_2_reads_memory_written_in_session_1(tmp_path: Path) -> None:
    """
    BDD Scenario #1
    ---------------
    Scenario: WEEK-4 MID-POINT GATE — session 2 reads memory written in session 1

    Given an EngagementOrchestrator wired with MemoryCore over a FileMemoryStore at tmp_path
    And write_back_outcome registered on AFTER_ENGAGEMENT
    When I run an engagement in session 1 (fresh orchestrator + store instance)
    And I construct a NEW orchestrator and NEW FileMemoryStore over the SAME path and run session 2
    Then session 2's assemble_working_memory (or store.get)
        surfaces the outcome written in session 1
    And the outcome reached the store via MemoryCore.ingest (a PreferenceSignal-shaped entry)
    """
    test_schema_1 = _schema()
    test_skill_registry_1 = _skills()

    first_memory = RecordingMemoryCore(
        schema=test_schema_1, store=FileMemoryStore(path=tmp_path / "mem.json")
    )

    # Given an EngagementOrchestrator wired with MemoryCore over a FileMemoryStore at tmp_path
    test_hooks = HookRegistry()
    # And write_back_outcome registered on AFTER_ENGAGEMENT
    test_hooks.register(event=HookEvent.AFTER_ENGAGEMENT, fn=write_back_outcome)

    first_orchestrator = EngagementOrchestrator(
        schema=test_schema_1,
        runner=WritebackRunner(),
        memory=first_memory,
        skills=test_skill_registry_1,
        hooks=test_hooks,
    )

    test_subject_id = uuid4()

    # When I run an engagement in session 1 (fresh orchestrator + store instance)
    await first_orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=test_subject_id,
        thread_id="thread-1",
    )

    # And I construct a NEW orchestrator and NEW FileMemoryStore over the SAME path
    test_schema_2 = _schema()
    test_skill_registry_2 = _skills()
    # ^ To avoid object reuse

    second_memory = MemoryCore(
        schema=test_schema_2, store=FileMemoryStore(path=tmp_path / "mem.json")
    )

    second_orchestrator = EngagementOrchestrator(
        schema=test_schema_2,
        runner=WritebackRunner(),
        memory=second_memory,
        skills=test_skill_registry_2,
    )
    # ...and run session 2
    await second_orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=test_subject_id,
        thread_id="thread-2",
    )

    # Then session 2's assemble_working_memory (or store.get)
    #   surfaces the outcome written in session 1
    second_working_memory_entries = (
        await second_orchestrator.memory.assemble_working_memory(subject_id=test_subject_id)
    ).entries
    first_memory_entries = await first_memory.store.get(subject_id=test_subject_id)
    assert all(entry in first_memory_entries for entry in second_working_memory_entries)

    # And the outcome reached the store via MemoryCore.ingest (a PreferenceSignal-shaped entry)
    assert len(first_memory.ingest_calls) == 1
    assert isinstance(first_memory.ingest_calls[0][1], PreferenceSignal)


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

    async def record_payloads_after(context: HookContext):
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

    assert uuid5(NAMESPACE_URL, "primer-core:skill:foundational") in [
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

    test_hooks = HookRegistry()
    test_hooks.register(event=HookEvent.AFTER_ENGAGEMENT, fn=write_back_outcome)

    first_orchestrator = EngagementOrchestrator(
        schema=test_schema,
        runner=WritebackRunner(),
        memory=first_memory,
        skills=test_skill_registry,
        hooks=test_hooks,
    )

    first_orchestrator.run_engagement(
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
        schema=test_schema, runner=RunWorkflowPort(), memory=second_memory, skills=_skills()
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
