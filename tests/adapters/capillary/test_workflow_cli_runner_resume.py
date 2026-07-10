import json
from uuid import uuid4

from capillary_actions_sdk.events import AGUIEventType
from capillary_actions_sdk.ports.platform import ResumeWorkflowRequest

from primer_core.adapters.capillary.workflow_cli_runner import WorkflowCliRunner


class FakeExec:
    def __init__(self, rc: int, stdout: str, stderr: str = "") -> None:
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[list[str]] = []

    async def __call__(self, args: list[str]) -> tuple[int, str, str]:
        self.calls.append(args)
        return self.rc, self.stdout, self.stderr


async def test_resume_sync_approve_uses_workflow_review_approve_json() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=0, stdout='{"run_id": "run-123", "status": "completed"}')
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == "run-123"
    assert response.status == "completed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "review"]
    assert str(workflow_run_id) in args
    assert "--approve" in args
    assert "--json" in args


async def test_resume_sync_input_data_uses_workflow_input_data_json() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data={"text": "hi"},
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == "run-123"
    assert response.status == "completed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "input"]
    assert str(workflow_run_id) in args
    assert "--data" in args
    assert "--json" in args
    assert json.loads(args[args.index("--data") + 1]) == {"text": "hi"}


async def test_resume_sync_nonzero_exit_returns_failed_response() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=2, stdout="", stderr="workflow failed")
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == ""
    assert response.status == "failed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "review"]
    assert str(workflow_run_id) in args
    assert "--approve" in args


async def test_resume_sync_invalid_json_returns_failed_response() -> None:
    fake_exec = FakeExec(rc=0, stdout="not-json")
    request = ResumeWorkflowRequest(
        workflow_run_id=uuid4(),
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == ""
    assert response.status == "failed"


async def test_resume_sync_invalid_request_returns_failed_response_without_exec() -> None:
    fake_exec = FakeExec(rc=0, stdout='{"run_id": "run-123", "status": "completed"}')
    request = ResumeWorkflowRequest(
        workflow_run_id=uuid4(),
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == ""
    assert response.status == "failed"
    assert fake_exec.calls == []


async def test_reject_uses_workflow_review_reject_and_comment_when_given() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment="Not ready yet",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.reject(request)

    assert response.run_id == "run-123"
    assert response.status == "completed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "review"]
    assert str(workflow_run_id) in args
    assert "--reject" in args
    assert "--json" in args
    assert "--comment" in args
    assert args[args.index("--comment") + 1] == "Not ready yet"


async def test_reject_without_comment_returns_failed_response_without_exec() -> None:
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = ResumeWorkflowRequest(
        workflow_run_id=uuid4(),
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.reject(request)

    assert response.run_id == ""
    assert response.status == "failed"
    assert fake_exec.calls == []


async def test_reject_nonzero_exit_returns_failed_response() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=2, stdout="", stderr="workflow failed")
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment="Not ready yet",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.reject(request)

    assert response.run_id == ""
    assert response.status == "failed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "review"]
    assert str(workflow_run_id) in args
    assert "--reject" in args
    assert "--comment" in args


async def test_reject_invalid_json_returns_failed_response() -> None:
    fake_exec = FakeExec(rc=0, stdout="not-json")
    request = ResumeWorkflowRequest(
        workflow_run_id=uuid4(),
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment="Not ready yet",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.reject(request)

    assert response.run_id == ""
    assert response.status == "failed"


async def test_resume_streams_agui_events_for_approve_review() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(
        rc=0,
        stdout=(
            '{"type": "RUN_STARTED", "thread_id": "thread-1", "run_id": "run-123"}\n'
            '{"type": "TEXT_MESSAGE_CONTENT", "thread_id": "thread-1", "run_id": "run-123", '
            '"message_id": "msg-1", "content": "Approved"}\n'
            '{"type": "RUN_FINISHED", "thread_id": "thread-1", "run_id": "run-123"}\n'
        ),
    )
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.resume(request)]

    assert [event.event_type for event in events] == [
        AGUIEventType.RUN_STARTED,
        AGUIEventType.TEXT_MESSAGE_CONTENT,
        AGUIEventType.RUN_FINISHED,
    ]

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "review"]
    assert str(workflow_run_id) in args
    assert "--approve" in args
    assert "--stream" in args
    assert "--json" in args


async def test_resume_streams_agui_events_for_input_data() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(
        rc=0,
        stdout=(
            '{"type": "RUN_STARTED", "thread_id": "thread-1", "run_id": "run-123"}\n'
            '{"type": "TEXT_MESSAGE_CONTENT", "thread_id": "thread-1", "run_id": "run-123", '
            '"message_id": "msg-1", "content": "Received input"}\n'
            '{"type": "RUN_FINISHED", "thread_id": "thread-1", "run_id": "run-123"}\n'
        ),
    )
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data={"text": "hi"},
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.resume(request)]

    assert [event.event_type for event in events] == [
        AGUIEventType.RUN_STARTED,
        AGUIEventType.TEXT_MESSAGE_CONTENT,
        AGUIEventType.RUN_FINISHED,
    ]

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "input"]
    assert str(workflow_run_id) in args
    assert "--data" in args
    assert "--stream" in args
    assert "--json" in args
    assert json.loads(args[args.index("--data") + 1]) == {"text": "hi"}


async def test_resume_nonzero_exit_yields_single_run_error_event() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=2, stdout="", stderr="workflow failed")
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.resume(request)]

    assert len(events) == 1
    assert events[0].event_type == AGUIEventType.RUN_ERROR
    assert events[0].thread_id == "thread-1"
    assert events[0].run_id == str(workflow_run_id)


async def test_resume_invalid_request_yields_single_run_error_event_without_exec() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=0, stdout="")
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.resume(request)]

    assert len(events) == 1
    assert events[0].event_type == AGUIEventType.RUN_ERROR
    assert events[0].thread_id == "thread-1"
    assert events[0].run_id == str(workflow_run_id)
    assert fake_exec.calls == []
