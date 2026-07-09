from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from capillary_actions_sdk.events import (
    AGUIEvent,
    AGUIEventType,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
)
from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)

from primer_core.orchestrator import EngagementOrchestrator
from primer_core.skills import SkillRegistry


class RecordingStreamingRunner(RunWorkflowPort):
    def __init__(self) -> None:
        self.requests: list[RunWorkflowRequest] = []
        self.run_sync_called = False

    async def run_sync(self, request: RunWorkflowRequest) -> RunWorkflowResponse:
        self.run_sync_called = True
        raise AssertionError("run_engagement_streaming should not call run_sync")

    async def run(self, request: RunWorkflowRequest) -> AsyncIterator[AGUIEvent]:
        self.requests.append(request)
        yield RunStartedEvent(thread_id=request.thread_id, run_id="run-123")
        yield TextMessageContentEvent(
            thread_id=request.thread_id,
            run_id="run-123",
            message_id="msg-1",
            content="Hello learner",
        )
        yield RunFinishedEvent(thread_id=request.thread_id, run_id="run-123")


class RecordingEventStream:
    def __init__(self) -> None:
        self.events: list[AGUIEvent] = []

    async def send_event(self, event: AGUIEvent) -> None:
        self.events.append(event)


def _skills() -> SkillRegistry:
    skills = SkillRegistry()
    skills.register("tutor-concept", "src/primer_core/wdfs/tutor-concept.yaml")
    return skills


async def test_run_engagement_streaming_yields_runner_events() -> None:
    runner = RecordingStreamingRunner()
    skills = _skills()
    orchestrator = EngagementOrchestrator(
        schema=object(),
        runner=runner,
        memory=object(),
        skills=skills,
    )

    subject_id = uuid4()
    input_data = {"question": "What is recursion?"}

    events = [
        event
        async for event in orchestrator.run_engagement_streaming(
            "tutor-concept",
            subject_id,
            thread_id="thread-1",
            input_data=input_data,
        )
    ]

    assert [event.event_type for event in events] == [
        AGUIEventType.RUN_STARTED,
        AGUIEventType.TEXT_MESSAGE_CONTENT,
        AGUIEventType.RUN_FINISHED,
    ]

    assert runner.run_sync_called is False
    assert len(runner.requests) == 1

    request = runner.requests[0]

    assert isinstance(request.workflow_id, UUID)
    assert request.workflow_id == skills.workflow_id("tutor-concept")
    assert request.thread_id == "thread-1"
    assert request.input_data == input_data
    assert request.org_id is None


async def test_run_engagement_streaming_forwards_events_to_event_stream() -> None:
    runner = RecordingStreamingRunner()
    event_stream = RecordingEventStream()
    orchestrator = EngagementOrchestrator(
        schema=object(),
        runner=runner,
        memory=object(),
        skills=_skills(),
    )

    events = [
        event
        async for event in orchestrator.run_engagement_streaming(
            "tutor-concept",
            uuid4(),
            thread_id="thread-1",
            input_data=None,
            event_stream=event_stream,
        )
    ]

    assert event_stream.events == events
    assert [event.event_type for event in events] == [
        AGUIEventType.RUN_STARTED,
        AGUIEventType.TEXT_MESSAGE_CONTENT,
        AGUIEventType.RUN_FINISHED,
    ]
