import json
from uuid import UUID, uuid4

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


def _resume_request(
    *,
    workflow_run_id: UUID,
    thread_id: str,
    decision: str | None,
    input_data: dict | None,
    comment: str | None,
    node_id: str | None = None,
) -> ResumeWorkflowRequest:
    request = ResumeWorkflowRequest(
        workflow_run_id=workflow_run_id,
        thread_id=thread_id,
        decision=decision,
        input_data=input_data,
        comment=comment,
    )

    if node_id is not None:
        request.node_id = node_id

    return request


async def test_resume_sync_approve_uses_workflow_review_approve_json_yes() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=0, stdout='{"run_id": "run-123", "status": "completed"}')
    request = _resume_request(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == "run-123"
    assert response.status == "completed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args == [
        "workflow",
        "review",
        "--run-id",
        str(workflow_run_id),
        "--node-id",
        "node-123",
        "--approve",
        "--json",
        "--yes",
    ]


async def test_resume_sync_input_data_uses_workflow_input_data_json_yes() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = _resume_request(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data={"text": "hi"},
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == "run-123"
    assert response.status == "completed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "input"]
    assert "--run-id" in args
    assert args[args.index("--run-id") + 1] == str(workflow_run_id)
    assert "--node-id" in args
    assert args[args.index("--node-id") + 1] == "node-123"
    assert "--data" in args
    assert json.loads(args[args.index("--data") + 1]) == {"text": "hi"}
    assert "--json" in args
    assert "--yes" in args
    assert "--thread-id" not in args
    assert "--stream" not in args


async def test_resume_sync_nonzero_exit_returns_failed_response() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=2, stdout="", stderr="workflow failed")
    request = _resume_request(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == ""
    assert response.status == "failed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "review"]
    assert "--run-id" in args
    assert args[args.index("--run-id") + 1] == str(workflow_run_id)
    assert "--node-id" in args
    assert args[args.index("--node-id") + 1] == "node-123"
    assert "--approve" in args


async def test_resume_sync_invalid_json_returns_failed_response() -> None:
    fake_exec = FakeExec(rc=0, stdout="not-json")
    request = _resume_request(
        workflow_run_id=uuid4(),
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == ""
    assert response.status == "failed"


async def test_resume_sync_missing_node_id_returns_failed_response_without_exec() -> None:
    fake_exec = FakeExec(rc=0, stdout='{"run_id": "run-123", "status": "completed"}')
    request = _resume_request(
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
    assert fake_exec.calls == []


async def test_resume_sync_invalid_request_returns_failed_response_without_exec() -> None:
    fake_exec = FakeExec(rc=0, stdout='{"run_id": "run-123", "status": "completed"}')
    request = _resume_request(
        workflow_run_id=uuid4(),
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)

    assert response.run_id == ""
    assert response.status == "failed"
    assert fake_exec.calls == []


async def test_reject_uses_workflow_review_reject_comment_json_yes() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = _resume_request(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment="Not ready yet",
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.reject(request)

    assert response.run_id == "run-123"
    assert response.status == "completed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args == [
        "workflow",
        "review",
        "--run-id",
        str(workflow_run_id),
        "--node-id",
        "node-123",
        "--reject",
        "--comment",
        "Not ready yet",
        "--json",
        "--yes",
    ]


async def test_reject_without_comment_returns_failed_response_without_exec() -> None:
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = _resume_request(
        workflow_run_id=uuid4(),
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.reject(request)

    assert response.run_id == ""
    assert response.status == "failed"
    assert fake_exec.calls == []


async def test_reject_without_node_id_returns_failed_response_without_exec() -> None:
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = _resume_request(
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
    assert fake_exec.calls == []


async def test_reject_nonzero_exit_returns_failed_response() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=2, stdout="", stderr="workflow failed")
    request = _resume_request(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment="Not ready yet",
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.reject(request)

    assert response.run_id == ""
    assert response.status == "failed"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "review"]
    assert "--run-id" in args
    assert args[args.index("--run-id") + 1] == str(workflow_run_id)
    assert "--node-id" in args
    assert args[args.index("--node-id") + 1] == "node-123"
    assert "--reject" in args
    assert "--comment" in args


async def test_reject_invalid_json_returns_failed_response() -> None:
    fake_exec = FakeExec(rc=0, stdout="not-json")
    request = _resume_request(
        workflow_run_id=uuid4(),
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment="Not ready yet",
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.reject(request)

    assert response.run_id == ""
    assert response.status == "failed"


async def test_resume_yields_run_finished_after_successful_approve_review() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = _resume_request(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.resume(request)]

    assert len(events) == 1
    assert events[0].event_type == AGUIEventType.RUN_FINISHED
    assert events[0].thread_id == "thread-1"
    assert events[0].run_id == "run-123"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "review"]
    assert "--stream" not in args
    assert "--thread-id" not in args


async def test_resume_yields_run_finished_after_successful_input_data() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = _resume_request(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data={"text": "hi"},
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.resume(request)]

    assert len(events) == 1
    assert events[0].event_type == AGUIEventType.RUN_FINISHED
    assert events[0].thread_id == "thread-1"
    assert events[0].run_id == "run-123"

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "input"]
    assert "--stream" not in args
    assert "--thread-id" not in args


async def test_resume_nonzero_exit_yields_single_run_error_event() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=2, stdout="", stderr="workflow failed")
    request = _resume_request(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.resume(request)]

    assert len(events) == 1
    assert events[0].event_type == AGUIEventType.RUN_ERROR
    assert events[0].thread_id == "thread-1"
    assert events[0].run_id == str(workflow_run_id)


async def test_resume_missing_node_id_yields_single_run_error_event_without_exec() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=0, stdout="")
    request = _resume_request(
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
    assert fake_exec.calls == []


async def test_resume_invalid_request_yields_single_run_error_event_without_exec() -> None:
    workflow_run_id = uuid4()
    fake_exec = FakeExec(rc=0, stdout="")
    request = _resume_request(
        workflow_run_id=workflow_run_id,
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment=None,
        node_id="node-123",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.resume(request)]

    assert len(events) == 1
    assert events[0].event_type == AGUIEventType.RUN_ERROR
    assert events[0].thread_id == "thread-1"
    assert events[0].run_id == str(workflow_run_id)
    assert fake_exec.calls == []
