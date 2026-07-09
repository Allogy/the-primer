import json
from collections.abc import AsyncIterator, Awaitable, Callable

from capillary_actions_sdk.events import (
    AGUIEvent,
    AGUIEventType,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from capillary_actions_sdk.ports.platform import (
    ResumeWorkflowPort,
    ResumeWorkflowRequest,
    ResumeWorkflowResponse,
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)
from pydantic import ValidationError

ExecCmd = Callable[[list[str]], Awaitable[tuple[int, str, str]]]


_EVENT_CLASS_BY_TYPE: dict[AGUIEventType, type[AGUIEvent]] = {
    AGUIEventType.RUN_STARTED: RunStartedEvent,
    AGUIEventType.TEXT_MESSAGE_START: TextMessageStartEvent,
    AGUIEventType.TEXT_MESSAGE_CONTENT: TextMessageContentEvent,
    AGUIEventType.TEXT_MESSAGE_END: TextMessageEndEvent,
    AGUIEventType.RUN_ERROR: RunErrorEvent,
    AGUIEventType.RUN_FINISHED: RunFinishedEvent,
}


def _parse_event_line(line: str) -> AGUIEvent | None:
    if not line.strip():
        return None

    try:
        raw_event = json.loads(line)
    except json.JSONDecodeError:
        return None

    try:
        event_type = AGUIEventType(raw_event.get("type"))
    except ValueError:
        return None

    event_class = _EVENT_CLASS_BY_TYPE.get(event_type)
    if event_class is None:
        return None

    payload = {**raw_event, "event_type": event_type}
    payload.pop("type", None)

    try:
        return event_class.model_validate(payload)
    except ValidationError:
        return None


class WorkflowCliRunner(RunWorkflowPort, ResumeWorkflowPort):
    def __init__(self, exec_cmd: ExecCmd) -> None:
        self._exec_cmd = exec_cmd

    async def run(self, request: RunWorkflowRequest) -> AsyncIterator[AGUIEvent]:
        cli_args = [
            "workflow",
            "run",
            str(request.workflow_id),
            "--thread-id",
            request.thread_id,
            "--input",
            json.dumps(request.input_data),
            "--json",
            "--stream",
        ]

        rc, stdout, stderr = await self._exec_cmd(cli_args)
        if rc != 0:
            yield RunErrorEvent(
                thread_id=request.thread_id,
                run_id="",
                error=stderr,
                code=str(rc),
            )
            return

        for line in stdout.splitlines():
            event = _parse_event_line(line)
            if event is not None:
                yield event

    async def run_sync(self, request: RunWorkflowRequest) -> RunWorkflowResponse:
        cli_args = [
            "workflow",
            "run",
            str(request.workflow_id),
            "--thread-id",
            request.thread_id,
            "--input",
            json.dumps(request.input_data),
            "--json",
        ]

        rc, stdout, stderr = await self._exec_cmd(cli_args)
        if rc != 0:
            return RunWorkflowResponse(run_id="", output={"error": stderr}, status="failed")

        parsed = json.loads(stdout)
        return RunWorkflowResponse(
            run_id=parsed["run_id"], output=parsed["output"], status=parsed["status"]
        )

    async def resume(self, request: ResumeWorkflowRequest) -> AsyncIterator[AGUIEvent]:
        if request.decision == "approve":
            cli_args = [
                "workflow",
                "review",
                request.workflow_run_id,
                "--thread-id",
                request.thread_id,
                "--approve",
                "--json",
                "--stream",
            ]

        elif request.input_data is not None:
            cli_args = [
                "workflow",
                "input",
                request.workflow_run_id,
                "--thread-id",
                request.thread_id,
                "--data",
                json.dumps(request.input_data),
                "--json",
                "--stream",
            ]

        else:
            yield RunErrorEvent(
                thread_id=request.thread_id,
                run_id=request.workflow_run_id,
                error="resume request must include a decision or input_data",
                code="invalid_request",
            )
            return

        rc, stdout, stderr = await self._exec_cmd(cli_args)
        if rc != 0:
            yield RunErrorEvent(
                thread_id=request.thread_id,
                run_id=request.workflow_run_id,
                error=stderr,
                code=str(rc),
            )
            return

        for line in stdout.splitlines():
            event = _parse_event_line(line)
            if event is not None:
                yield event

    async def resume_sync(self, request: ResumeWorkflowRequest) -> ResumeWorkflowResponse:
        if request.decision == "approve":
            cli_args = [
                "workflow",
                "review",
                request.workflow_run_id,
                "--thread-id",
                request.thread_id,
                "--approve",
                "--json",
            ]

        elif request.input_data is not None:
            cli_args = [
                "workflow",
                "input",
                request.workflow_run_id,
                "--thread-id",
                request.thread_id,
                "--data",
                json.dumps(request.input_data),
                "--json",
            ]

        else:
            return ResumeWorkflowResponse(run_id="", status="failed")

        rc, stdout, _stderr = await self._exec_cmd(cli_args)
        if rc != 0:
            return ResumeWorkflowResponse(run_id="", status="failed")

        parsed = json.loads(stdout)
        return ResumeWorkflowResponse(
            run_id=parsed["run_id"],
            status=parsed["status"],
        )

    async def reject(self, request: ResumeWorkflowRequest) -> ResumeWorkflowResponse:
        cli_args = [
            "workflow",
            "review",
            request.workflow_run_id,
            "--thread-id",
            request.thread_id,
            "--reject",
            "--json",
        ]

        if request.comment is not None:
            cli_args.extend(["--comment", request.comment])

        rc, stdout, _stderr = await self._exec_cmd(cli_args)
        if rc != 0:
            return ResumeWorkflowResponse(run_id="", status="failed")

        parsed = json.loads(stdout)
        return ResumeWorkflowResponse(
            run_id=parsed["run_id"],
            status=parsed["status"],
        )
