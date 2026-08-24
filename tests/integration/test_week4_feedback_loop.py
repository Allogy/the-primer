"""Integration test for the Week-4 persistent feedback loop."""

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

from capillary_actions_sdk.events import AGUIEvent
from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)
from capillary_actions_sdk.schema.domain_schema import load

import capillary_actions_sdk
from primer_core.adapters.capillary.file_memory_store import FileMemoryStore
from primer_core.memory.core import MemoryCore
from primer_core.orchestrator import (
    EngagementOrchestrator,
    HookEvent,
    HookRegistry,
    write_back_outcome,
)
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
                "answer": "Recursion calls itself.",
                "writeback": {
                    "dimension": "history",
                    "content": {
                        "courses": ["recursion"],
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


def _education_manifest_path() -> Path:
    return (
        Path(capillary_actions_sdk.__file__).parent
        / "schema"
        / "examples"
        / "education.manifest.yaml"
    )


def _skills() -> SkillRegistry:
    skills = SkillRegistry()
    skills.register(
        "tutor-concept",
        "src/primer_core/wdfs/tutor-concept.yaml",
    )
    return skills


async def test_after_engagement_writeback_persists_across_store_instances(
    tmp_path: Path,
) -> None:
    schema = load(str(_education_manifest_path()))
    subject_id = uuid4()
    memory_path = tmp_path / "week4-memory.json"

    first_memory = MemoryCore(
        schema=schema,
        store=FileMemoryStore(memory_path),
    )

    hooks = HookRegistry()
    hooks.register(
        HookEvent.AFTER_ENGAGEMENT,
        write_back_outcome,
    )

    runner = WritebackRunner()

    orchestrator = EngagementOrchestrator(
        schema=schema,
        runner=runner,
        memory=first_memory,
        skills=_skills(),
        hooks=hooks,
    )

    response = await orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=subject_id,
        thread_id="thread-1",
        input_data={
            "question": "What is recursion?",
        },
    )

    assert response.status == "completed"
    assert len(runner.requests) == 1

    second_memory = MemoryCore(
        schema=schema,
        store=FileMemoryStore(memory_path),
    )

    working_memory = await second_memory.assemble_working_memory(subject_id)

    assert len(working_memory.entries) == 1

    persisted_entry = working_memory.entries[0]

    assert persisted_entry.tier == "long_term"
    assert persisted_entry.dimension == "history"
    assert persisted_entry.content == {
        "courses": ["recursion"],
    }
    assert persisted_entry.metadata["source"] == ("primer_core.orchestrator")
    assert "signal_id" in persisted_entry.metadata
