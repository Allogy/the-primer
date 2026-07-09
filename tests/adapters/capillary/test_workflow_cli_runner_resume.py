import json

from capillary_actions_sdk.events import AGUIEventType
from capillary_actions_sdk.ports.platform import ResumeWorkflowRequest

from primer_core.adapters.capillary.workflow_cli_runner import WorkflowCliRunner

class FakeExec:
    def __init__(self, rc: int, stdout: str, stderr: str = ""):
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr
        self.calls = []
    
    async def __call__(self, args: list[str]) -> tuple[int, str, str]:
        self.calls.append(args)
        return self.rc, self.stdout, self.stderr
    

async def test_resume_sync_approve_uses_workflow_review_approve_json() -> None:
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}'
    )
    request = ResumeWorkflowRequest(
        workflow_run_id="run-123",
        thread_id="thread-1",
        decision="approve",
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)
    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert response.run_id == "run-123"
    assert response.status == "completed"
    assert len(fake_exec.calls) == 1

    assert args[:2] == ["workflow", "review"]
    assert "--approve" in args
    assert "--json" in args


async def test_resume_sync_input_data_uses_workflow_input_data_json() -> None:
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = ResumeWorkflowRequest(
        workflow_run_id="run-123",
        thread_id="thread-1",
        decision=None,
        input_data={"text": "hi"},
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.resume_sync(request)
    args = fake_exec.calls[0]

    assert response.run_id == "run-123"
    assert response.status == "completed"

    assert args[:2] == ["workflow", "input"]
    assert "--data" in args
    assert "--json" in args
    assert json.loads(args[args.index("--data") + 1]) == {"text": "hi"}


async def test_reject_uses_workflow_review_reject_and_comment_when_given() -> None:
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = ResumeWorkflowRequest(
        workflow_run_id="run-123",
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment="Not ready yet",
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.reject(request)

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert response.run_id == "run-123"
    assert response.status == "completed"

    assert args[:2] == ["workflow", "review"]
    assert "--reject" in args
    assert "--json" in args
    assert "--comment" in args
    assert args[args.index("--comment") + 1] == "Not ready yet"


async def test_reject_omits_comment_when_not_given() -> None:
    fake_exec = FakeExec(
        rc=0,
        stdout='{"run_id": "run-123", "status": "completed"}',
    )
    request = ResumeWorkflowRequest(
        workflow_run_id="run-123",
        thread_id="thread-1",
        decision=None,
        input_data=None,
        comment=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    await runner.reject(request)

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert "--reject" in args
    assert "--comment" not in args


async def test_resume_streams_agui_events_for_approve_review() -> None:
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
        workflow_run_id="run-123",
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
    assert "--approve" in args
    assert "--stream" in args
    assert "--json" in args