import importlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from capillary_actions_sdk.events import AGUIEventType
from capillary_actions_sdk.models.student_model import PreferenceSignal
from capillary_actions_sdk.schema.domain_schema import load

import capillary_actions_sdk
from primer_core.adapters.capillary.kb_pgvector import PgVectorKnowledgeBase
from primer_core.adapters.capillary.workflow_cli_runner import WorkflowCliRunner
from primer_core.memory.core import MemoryCore
from primer_core.orchestrator import EngagementOrchestrator
from primer_core.skills import SkillRegistry


class FakeExec:
    def __init__(self, rc: int, stdout: str, stderr: str = "") -> None:
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[list[str]] = []

    async def __call__(self, args: list[str]) -> tuple[int, str, str]:
        self.calls.append(args)
        return self.rc, self.stdout, self.stderr


class FakePgVectorSearchClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], int]] = []

    async def search(
        self,
        query: str,
        kb_names: list[str],
        top_k: int,
    ) -> list[dict]:
        self.calls.append((query, kb_names, top_k))
        return [
            {
                "text": "A derivative measures instantaneous rate of change.",
                "score": 0.95,
            },
            {
                "chunk": "A tangent line approximates local behavior.",
                "distance": 0.20,
            },
        ]


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


def _optional_class(module_name: str, class_name: str):
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        pytest.skip(f"{module_name}.{class_name} has not landed in this branch yet")

    try:
        return getattr(module, class_name)
    except AttributeError:
        pytest.skip(f"{module_name}.{class_name} has not landed in this branch yet")


async def test_week_3_gate_streams_education_engagement_through_workflow_runner_port() -> None:
    schema = load(str(_education_manifest_path()))
    subject_id = uuid4()
    fake_exec = FakeExec(
        rc=0,
        stdout=(
            '{"type": "RUN_STARTED", "thread_id": "thread-1", "run_id": "run-123"}\n'
            '{"type": "TEXT_MESSAGE_CONTENT", "thread_id": "thread-1", "run_id": "run-123", '
            '"message_id": "msg-1", "content": "Tutoring content"}\n'
            '{"type": "RUN_FINISHED", "thread_id": "thread-1", "run_id": "run-123"}\n'
            '{"run_id": "run-123", "workflow_id": "workflow-123", '
            '"final_status": "completed", "node_outputs": {"answer": "ok"}}\n'
        ),
    )
    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    skills = _skills()

    orchestrator = EngagementOrchestrator(
        schema=schema,
        runner=runner,
        memory=object(),
        skills=skills,
    )

    events = [
        event
        async for event in orchestrator.run_engagement_streaming(
            "tutor-concept",
            subject_id,
            thread_id="thread-1",
            input_data={"concept": "derivatives"},
        )
    ]

    assert [event.event_type for event in events] == [
        AGUIEventType.RUN_STARTED,
        AGUIEventType.TEXT_MESSAGE_CONTENT,
        AGUIEventType.RUN_FINISHED,
    ]

    assert len(fake_exec.calls) == 1

    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "run"]
    assert "--json" in args
    assert "--input" in args
    assert "--stream" not in args
    assert "--thread-id" not in args

    input_index = args.index("--input")
    assert json.loads(args[input_index + 1]) == {"concept": "derivatives"}


async def test_week_3_gate_file_memory_store_persists_entries_across_instances(
    tmp_path,
) -> None:
    FileMemoryStore = _optional_class(
        "primer_core.adapters.capillary.file_memory_store",
        "FileMemoryStore",
    )

    schema = load(str(_education_manifest_path()))
    subject_id = uuid4()
    memory_path = tmp_path / "memory.json"

    first_memory = MemoryCore(
        schema=schema,
        store=FileMemoryStore(memory_path),
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

    ingested_entry = await first_memory.ingest(
        subject_id=subject_id,
        signal=signal,
    )

    second_memory = MemoryCore(
        schema=schema,
        store=FileMemoryStore(memory_path),
    )

    working_memory = await second_memory.assemble_working_memory(subject_id)

    assert any(entry.id == ingested_entry.id for entry in working_memory.entries)
    assert any(
        entry.dimension == "history" and entry.content == {"courses": ["calculus"]}
        for entry in working_memory.entries
    )


async def test_week_3_gate_pgvector_knowledge_base_adapter_retrieves_chunks() -> None:
    client = FakePgVectorSearchClient()
    kb = PgVectorKnowledgeBase(client=client)

    chunks = await kb.retrieve(
        "teach me derivatives",
        ["primer-education-kb"],
        top_k=2,
    )

    assert client.calls == [
        (
            "teach me derivatives",
            ["primer-education-kb"],
            2,
        )
    ]

    assert len(chunks) == 2
    assert chunks[0].text == "A derivative measures instantaneous rate of change."
    assert chunks[0].score == 0.95
    assert chunks[1].text == "A tangent line approximates local behavior."
    assert chunks[1].score == 0.80
