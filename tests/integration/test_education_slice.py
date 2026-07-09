from pathlib import Path
from uuid import uuid4

from capillary_actions_sdk.models.knowledge import RetrievedChunk
from capillary_actions_sdk.models.student_model import PreferenceSignal
from capillary_actions_sdk.ports.platform import RunWorkflowResponse
from capillary_actions_sdk.reference.in_memory_memory_store import InMemoryMemoryStore
from capillary_actions_sdk.schema.domain_schema import load
from pydantic_ai.models.test import TestModel

import capillary_actions_sdk
from primer_core.interaction import InteractionAgent
from primer_core.memory.core import MemoryCore
from primer_core.orchestrator import EngagementOrchestrator
from primer_core.skills import SkillRegistry
from primer_core.testing.fakes import FakeKnowledgeBase, FakeRunWorkflowPort


def _education_manifest_path() -> Path:
    return (
        Path(capillary_actions_sdk.__file__).parent
        / "schema"
        / "examples"
        / "education.manifest.yaml"
    )


def _skills() -> SkillRegistry:
    skills = SkillRegistry()
    skills.register("tutor-concept", "src/primer_core/wdfs/tutor-concept.yaml")
    return skills


async def test_week_2_gate_end_to_end_education_engagement_runs_in_memory() -> None:
    schema = load(str(_education_manifest_path()))
    subject_id = uuid4()

    memory = MemoryCore(
        schema=schema,
        store=InMemoryMemoryStore(),
    )
    kb = FakeKnowledgeBase(
        [
            RetrievedChunk(
                text="A derivative measures instantaneous rate of change.",
                score=0.95,
            )
        ]
    )
    runner = FakeRunWorkflowPort(
        RunWorkflowResponse(
            run_id="run-123",
            output={"answer": "ok"},
            status="completed",
        )
    )
    skills = _skills()

    orchestrator = EngagementOrchestrator(
        schema=schema,
        runner=runner,
        memory=memory,
        skills=skills,
    )
    agent = InteractionAgent(
        schema=schema,
        kb=kb,
        memory=memory,
        model=TestModel(custom_output_text="Derivatives describe rates of change."),
    )

    signal = PreferenceSignal(
        id=uuid4(),
        user_id=subject_id,
        org_id=uuid4(),
        signal_type="short_term",
        payload={
            "dimension": "history",
            "content": {"courses": ["calculus"]},
        },
        source="test",
    )

    ingested_entry = await memory.ingest(subject_id=subject_id, signal=signal)
    engagement_response = await orchestrator.run_engagement(
        "tutor-concept",
        subject_id,
        "thread-1",
        input_data={"concept": "derivatives"},
    )
    agent_response = await agent.turn(subject_id, "teach me derivatives")

    assert list(schema.knowledge_base.kb_names) == ["primer-education-kb"]

    assert ingested_entry.dimension == "history"
    assert ingested_entry.content == {"courses": ["calculus"]}

    assert engagement_response.status == "completed"
    assert engagement_response.output == {"answer": "ok"}

    assert len(runner.requests) == 1
    assert runner.requests[0].workflow_id == skills.workflow_id("tutor-concept")
    assert runner.requests[0].thread_id == "thread-1"
    assert runner.requests[0].input_data == {"concept": "derivatives"}

    assert agent_response == "Derivatives describe rates of change."
    assert kb.calls == [
        (
            "teach me derivatives",
            ["primer-education-kb"],
            5,
        )
    ]

    working_memory = await memory.assemble_working_memory(subject_id)
    assert working_memory.learner_id == subject_id
    assert ingested_entry in working_memory.entries
