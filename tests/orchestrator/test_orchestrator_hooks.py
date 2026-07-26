"""Tests for hook integration in EngagementOrchestrator."""

from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID, uuid4

from capillary_actions_sdk.events import (
    AGUIEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
)
from capillary_actions_sdk.models.student_model import PreferenceSignal
from capillary_actions_sdk.ports.memory import MemoryStorePort
from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)
from capillary_actions_sdk.schema import (
    DimensionSpec,
    DomainSchema,
    KnowledgeBaseWiring,
)

from primer_core.memory import MemoryCore
from primer_core.orchestrator import (
    EngagementOrchestrator,
    HookContext,
    HookEvent,
    HookRegistry,
    on_struggle,
    write_back_outcome,
)
from primer_core.skills import SkillRegistry


class RecordingRunner(RunWorkflowPort):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.requests: list[RunWorkflowRequest] = []

    async def run_sync(
        self,
        request: RunWorkflowRequest,
    ) -> RunWorkflowResponse:
        self.calls.append("runner")
        self.requests.append(request)

        return RunWorkflowResponse(
            run_id="run-123",
            output={"answer": "Recursion calls itself."},
            status="completed",
        )

    async def run(
        self,
        request: RunWorkflowRequest,
    ) -> AsyncIterator[AGUIEvent]:
        raise AssertionError("run_engagement should not call the streaming runner")
        yield  # pragma: no cover


class RecordingWritebackRunner(RecordingRunner):
    async def run_sync(
        self,
        request: RunWorkflowRequest,
    ) -> RunWorkflowResponse:
        self.calls.append("runner")
        self.requests.append(request)

        return RunWorkflowResponse(
            run_id="run-123",
            output={
                "answer": "Recursion calls itself.",
                "writeback": {
                    "dimension": "history",
                    "content": {
                        "courses": ["recursion"],
                    },
                },
            },
            status="completed",
        )


class RecordingStruggleRunner(RecordingRunner):
    async def run_sync(
        self,
        request: RunWorkflowRequest,
    ) -> RunWorkflowResponse:
        self.calls.append("runner")
        self.requests.append(request)

        return RunWorkflowResponse(
            run_id="run-123",
            output={
                "answer": "The learner needs more support.",
                "struggling": True,
            },
            status="completed",
        )


class RecordingHookStreamingRunner(RunWorkflowPort):
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.requests: list[RunWorkflowRequest] = []

    async def run_sync(
        self,
        request: RunWorkflowRequest,
    ) -> RunWorkflowResponse:
        raise AssertionError("run_engagement_streaming should not call run_sync")

    async def run(
        self,
        request: RunWorkflowRequest,
    ) -> AsyncIterator[AGUIEvent]:
        self.calls.append("runner-start")
        self.requests.append(request)

        yield RunStartedEvent(
            thread_id=request.thread_id,
            run_id="run-123",
        )
        yield TextMessageContentEvent(
            thread_id=request.thread_id,
            run_id="run-123",
            message_id="message-1",
            content="Hello learner",
        )
        yield RunFinishedEvent(
            thread_id=request.thread_id,
            run_id="run-123",
        )

        self.calls.append("runner-finished")


class RecordingMemoryCore(MemoryCore):
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


def _memory(schema: DomainSchema) -> MemoryCore:
    store = cast(MemoryStorePort, object())
    return MemoryCore(schema=schema, store=store)


def _skills() -> SkillRegistry:
    skills = SkillRegistry()
    skills.register(
        "tutor-concept",
        "src/primer_core/wdfs/tutor-concept.yaml",
    )
    return skills


async def test_run_engagement_fires_hooks_before_and_after_with_context() -> None:
    calls: list[str] = []
    contexts: list[HookContext] = []
    payloads: list[dict] = []

    schema = _schema()
    memory = _memory(schema)
    runner = RecordingRunner(calls)
    hooks = HookRegistry()

    async def record_before(ctx: HookContext) -> None:
        calls.append("before")
        contexts.append(ctx)
        payloads.append(dict(ctx.payload))

    async def record_after(ctx: HookContext) -> None:
        calls.append("after")
        contexts.append(ctx)
        payloads.append(dict(ctx.payload))

    hooks.register(HookEvent.BEFORE_ENGAGEMENT, record_before)
    hooks.register(HookEvent.AFTER_ENGAGEMENT, record_after)

    orchestrator = EngagementOrchestrator(
        schema=schema,
        runner=runner,
        memory=memory,
        skills=_skills(),
        hooks=hooks,
    )

    subject_id = uuid4()
    input_data = {"question": "What is recursion?"}

    response = await orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=subject_id,
        thread_id="thread-1",
        input_data=input_data,
    )

    assert calls == ["before", "runner", "after"]

    assert len(contexts) == 2
    assert contexts[0] is contexts[1]

    for context in contexts:
        assert context.subject_id == subject_id
        assert context.schema is schema
        assert context.engagement == "tutor-concept"
        assert context.memory is memory

    assert payloads[0] == {
        "input": input_data,
    }

    assert payloads[1] == {
        "input": input_data,
        "outcome": {"answer": "Recursion calls itself."},
        "status": "completed",
        "run_id": "run-123",
    }

    assert response.run_id == "run-123"
    assert response.output == {"answer": "Recursion calls itself."}
    assert response.status == "completed"


async def test_run_engagement_remains_compatible_without_hooks() -> None:
    calls: list[str] = []

    schema = _schema()
    runner = RecordingRunner(calls)

    orchestrator = EngagementOrchestrator(
        schema=schema,
        runner=runner,
        memory=_memory(schema),
        skills=_skills(),
    )

    response = await orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=uuid4(),
        thread_id="thread-1",
    )

    assert calls == ["runner"]
    assert response.run_id == "run-123"
    assert response.output == {"answer": "Recursion calls itself."}
    assert response.status == "completed"

    assert len(runner.requests) == 1
    assert runner.requests[0].input_data == {}


async def test_run_engagement_streaming_fires_hooks_around_typed_events() -> None:
    calls: list[str] = []
    contexts: list[HookContext] = []
    after_payloads: list[dict] = []

    schema = _schema()
    memory = _memory(schema)
    hooks = HookRegistry()
    runner = RecordingHookStreamingRunner(calls)

    async def record_before(ctx: HookContext) -> None:
        calls.append("before")
        contexts.append(ctx)

    async def record_after(ctx: HookContext) -> None:
        calls.append("after")
        contexts.append(ctx)
        after_payloads.append(dict(ctx.payload))

    hooks.register(HookEvent.BEFORE_ENGAGEMENT, record_before)
    hooks.register(HookEvent.AFTER_ENGAGEMENT, record_after)

    orchestrator = EngagementOrchestrator(
        schema=schema,
        runner=runner,
        memory=memory,
        skills=_skills(),
        hooks=hooks,
    )

    subject_id = uuid4()
    input_data = {"question": "What is recursion?"}
    events: list[AGUIEvent] = []

    async for event in orchestrator.run_engagement_streaming(
        skill_name="tutor-concept",
        subject_id=subject_id,
        thread_id="thread-1",
        input_data=input_data,
    ):
        events.append(event)
        calls.append(f"consumer-{event.event_type.value}")

    assert calls == [
        "before",
        "runner-start",
        "consumer-RUN_STARTED",
        "consumer-TEXT_MESSAGE_CONTENT",
        "consumer-RUN_FINISHED",
        "runner-finished",
        "after",
    ]

    assert len(events) == 3
    assert all(isinstance(event, AGUIEvent) for event in events)

    assert len(contexts) == 2
    assert contexts[0] is contexts[1]

    for context in contexts:
        assert context.subject_id == subject_id
        assert context.schema is schema
        assert context.engagement == "tutor-concept"
        assert context.memory is memory

    assert after_payloads == [
        {
            "input": input_data,
            "outcome": events,
        }
    ]

    assert len(runner.requests) == 1
    assert runner.requests[0].thread_id == "thread-1"
    assert runner.requests[0].input_data == input_data


async def test_after_engagement_writeback_calls_memory_ingest() -> None:
    calls: list[str] = []
    schema = _schema()
    memory = RecordingMemoryCore()
    hooks = HookRegistry()

    hooks.register(
        HookEvent.AFTER_ENGAGEMENT,
        write_back_outcome,
    )

    orchestrator = EngagementOrchestrator(
        schema=schema,
        runner=RecordingWritebackRunner(calls),
        memory=memory,
        skills=_skills(),
        hooks=hooks,
    )

    subject_id = uuid4()

    await orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=subject_id,
        thread_id="thread-1",
    )

    assert len(memory.ingest_calls) == 1

    ingested_subject_id, signal = memory.ingest_calls[0]

    assert ingested_subject_id == subject_id
    assert signal.user_id == subject_id
    assert signal.payload == {
        "dimension": "history",
        "content": {
            "courses": ["recursion"],
        },
    }


async def test_run_engagement_fires_struggle_hook_and_sets_next_skill() -> None:
    calls: list[str] = []
    after_payloads: list[dict] = []

    schema = DomainSchema(
        domain="test-domain",
        subject="test-subject",
        dimensions=[],
        knowledge_base=KnowledgeBaseWiring(kb_names=[]),
        engagements=[
            "foundational",
            "tutor-concept",
        ],
    )
    hooks = HookRegistry()

    async def route_on_struggle(ctx: HookContext) -> None:
        calls.append("struggle")
        await on_struggle(ctx)

    async def record_after(ctx: HookContext) -> None:
        calls.append("after")
        after_payloads.append(dict(ctx.payload))

    hooks.register(
        HookEvent.ON_STRUGGLE_DETECTED,
        route_on_struggle,
    )
    hooks.register(
        HookEvent.AFTER_ENGAGEMENT,
        record_after,
    )

    orchestrator = EngagementOrchestrator(
        schema=schema,
        runner=RecordingStruggleRunner(calls),
        memory=_memory(schema),
        skills=_skills(),
        hooks=hooks,
    )

    await orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=uuid4(),
        thread_id="thread-1",
    )

    assert calls == [
        "runner",
        "struggle",
        "after",
    ]
    assert after_payloads[0]["struggling"] is True
    assert after_payloads[0]["next_skill"] == "foundational"
