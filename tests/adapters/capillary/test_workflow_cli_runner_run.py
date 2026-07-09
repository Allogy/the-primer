import json
from uuid import uuid4

from capillary_actions_sdk.events import AGUIEventType
from capillary_actions_sdk.ports.platform import (
    ResumeWorkflowPort,
    RunWorkflowPort,
    RunWorkflowRequest,
)

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


def test_workflow_cli_runner_implements_frozen_ports() -> None:
    fake_exec = FakeExec(rc=0, stdout="")
    runner = WorkflowCliRunner(exec_cmd=fake_exec)

    assert isinstance(runner, RunWorkflowPort)
    assert isinstance(runner, ResumeWorkflowPort)


async def test_run_sync_shells_workflow_run_json_and_parses_response() -> None:
    fake_exec = FakeExec(
        rc=0, stdout='{"run_id": "run-123", "status": "completed", "output": {"answer":"42"}}'
    )
    input_data = {"question": "What is recursion?"}
    request = RunWorkflowRequest(
        workflow_id=uuid4(),
        thread_id="thread-1",
        input_data=input_data,
        org_id=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.run_sync(request)

    assert response.run_id == "run-123"
    assert response.status == "completed"
    assert response.output == {"answer": "42"}

    assert len(fake_exec.calls) == 1
    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "run"]
    assert "--json" in args
    assert "--input" in args

    input_index = args.index("--input")
    assert json.loads(args[input_index + 1]) == input_data


async def test_run_sync_nonzero_exit_returns_failed_response() -> None:
    fake_exec = FakeExec(rc=2, stdout="", stderr="workflow failed")
    input_data = {"question": "What is recursion?"}
    request = RunWorkflowRequest(
        workflow_id=uuid4(),
        thread_id="thread-1",
        input_data=input_data,
        org_id=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    response = await runner.run_sync(request)
    args = fake_exec.calls[0]

    assert response.status == "failed"
    assert len(fake_exec.calls) == 1

    assert args[:2] == ["workflow", "run"]
    assert "--json" in args
    assert "--input" in args

    input_index = args.index("--input")
    assert json.loads(args[input_index + 1]) == input_data


async def test_run_streams_agui_events_from_ndjson_stdout() -> None:
    fake_exec = FakeExec(
        rc=0,
        stdout=(
            '{"type": "RUN_STARTED", "thread_id": "thread-1", "run_id": "run-123"}\n'
            '{"type": "TEXT_MESSAGE_CONTENT", "thread_id": "thread-1", "run_id": "run-123", '
            '"message_id": "msg-1", "content": "Hello"}\n'
            '{"type": "RUN_FINISHED", "thread_id": "thread-1", "run_id": "run-123"}\n'
        ),
    )
    input_data = {"question": "What is recursion?"}
    request = RunWorkflowRequest(
        workflow_id=uuid4(),
        thread_id="thread-1",
        input_data=input_data,
        org_id=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.run(request)]

    assert [event.event_type for event in events] == [
        AGUIEventType.RUN_STARTED,
        AGUIEventType.TEXT_MESSAGE_CONTENT,
        AGUIEventType.RUN_FINISHED,
    ]

    assert len(fake_exec.calls) == 1

    args = fake_exec.calls[0]

    assert args[:2] == ["workflow", "run"]
    assert "--stream" in args
    assert "--json" in args


async def test_run_skips_blank_invalid_json_and_unknown_event_lines() -> None:
    fake_exec = FakeExec(
        rc=0,
        stdout=(
            "\n"
            "not-json\n"
            '{"type": "RUN_STARTED", "thread_id": "thread-1", "run_id": "run-123"}\n'
            '{"type": "UNKNOWN_EVENT", "thread_id": "thread-1", "run_id": "run-123"}\n'
            '{"type": "TEXT_MESSAGE_CONTENT", "thread_id": "thread-1", "run_id": "run-123", '
            '"message_id": "msg-1", "content": "Hello"}\n'
            '{"type": "RUN_FINISHED", "thread_id": "thread-1", "run_id": "run-123"}\n'
        ),
    )
    request = RunWorkflowRequest(
        workflow_id=uuid4(),
        thread_id="thread-1",
        input_data={"question": "What is recursion?"},
        org_id=None,
    )

    runner = WorkflowCliRunner(exec_cmd=fake_exec)
    events = [event async for event in runner.run(request)]

    assert [event.event_type for event in events] == [
        AGUIEventType.RUN_STARTED,
        AGUIEventType.TEXT_MESSAGE_CONTENT,
        AGUIEventType.RUN_FINISHED,
    ]
