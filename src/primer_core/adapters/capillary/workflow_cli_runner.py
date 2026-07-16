from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

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
    AGUIEventType.RUN_FINISHED: RunFinishedEvent,
    AGUIEventType.RUN_ERROR: RunErrorEvent,
    AGUIEventType.TEXT_MESSAGE_START: TextMessageStartEvent,
    AGUIEventType.TEXT_MESSAGE_CONTENT: TextMessageContentEvent,
    AGUIEventType.TEXT_MESSAGE_END: TextMessageEndEvent,
}


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(value, dict):
        return None

    return value


def _parse_json_lines(stdout: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        parsed = _parse_json_object(line)
        if parsed is not None:
            objects.append(parsed)

    return objects


def _parse_event_line(line: str) -> AGUIEvent | None:
    raw_event = _parse_json_object(line)
    if raw_event is None:
        return None

    raw_type = raw_event.get("type")
    if raw_type is None:
        # The real `workflow run --json` stream ends with a final result object,
        # not an AG-UI event. Skip it in the streaming path.
        return None

    try:
        event_type = AGUIEventType(raw_type)
    except ValueError:
        return None

    event_class = _EVENT_CLASS_BY_TYPE.get(event_type)
    if event_class is None:
        return None

    try:
        return event_class.model_validate(raw_event)
    except ValidationError:
        return None


def _parse_run_response(stdout: str) -> RunWorkflowResponse | None:
    for obj in reversed(_parse_json_lines(stdout)):
        run_id = obj.get("run_id")

        if "final_status" in obj:
            status = obj.get("final_status")
            output = obj.get("node_outputs", {})
        else:
            status = obj.get("status")
            output = obj.get("output", {})

        if isinstance(run_id, str) and isinstance(status, str) and isinstance(output, dict):
            return RunWorkflowResponse(
                run_id=run_id,
                output=output,
                status=status,
            )

    return None


def _parse_resume_response(stdout: str) -> ResumeWorkflowResponse | None:
    for obj in reversed(_parse_json_lines(stdout)):
        run_id = obj.get("run_id")
        status = obj.get("status") or obj.get("final_status")

        if isinstance(run_id, str) and isinstance(status, str):
            return ResumeWorkflowResponse(
                run_id=run_id,
                status=status,
            )

    return None


class WorkflowCliRunner(RunWorkflowPort, ResumeWorkflowPort):
    """Run workflow executions through the real workflow CLI machine surface."""

    def __init__(self, exec_cmd: ExecCmd) -> None:
        self._exec_cmd = exec_cmd

    async def run_sync(self, request: RunWorkflowRequest) -> RunWorkflowResponse:
        cli_args = [
            "workflow",
            "run",
            str(request.workflow_id),
            "--input",
            json.dumps(request.input_data or {}),
            "--json",
        ]

        rc, stdout, stderr = await self._exec_cmd(cli_args)
        if rc != 0:
            return RunWorkflowResponse(
                run_id="",
                output={"error": stderr},
                status="failed",
            )

        response = _parse_run_response(stdout)
        if response is None:
            return RunWorkflowResponse(
                run_id="",
                output={"error": "workflow returned invalid JSON response"},
                status="failed",
            )

        return response

    async def run(self, request: RunWorkflowRequest) -> AsyncIterator[AGUIEvent]:
        cli_args = [
            "workflow",
            "run",
            str(request.workflow_id),
            "--input",
            json.dumps(request.input_data or {}),
            "--json",
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

    async def resume(self, request: ResumeWorkflowRequest) -> AsyncIterator[AGUIEvent]:
        response = await self.resume_sync(request)

        if response.status == "failed":
            yield RunErrorEvent(
                thread_id=request.thread_id,
                run_id=str(request.workflow_run_id),
                error="workflow resume failed",
                code="failed",
            )
            return

        yield RunFinishedEvent(
            thread_id=request.thread_id,
            run_id=response.run_id,
        )

    async def resume_sync(self, request: ResumeWorkflowRequest) -> ResumeWorkflowResponse:
        workflow_run_id = str(request.workflow_run_id)
        node_id = getattr(request, "node_id", None)

        if not node_id:
            return ResumeWorkflowResponse(
                run_id="",
                status="failed",
            )

        if request.decision == "approve":
            cli_args = [
                "workflow",
                "review",
                "--run-id",
                workflow_run_id,
                "--node-id",
                node_id,
                "--approve",
                "--json",
                "--yes",
            ]
        elif request.decision is None and request.input_data is not None:
            cli_args = [
                "workflow",
                "input",
                "--run-id",
                workflow_run_id,
                "--node-id",
                node_id,
                "--data",
                json.dumps(request.input_data),
                "--json",
                "--yes",
            ]
        else:
            return ResumeWorkflowResponse(
                run_id="",
                status="failed",
            )

        rc, stdout, _stderr = await self._exec_cmd(cli_args)
        if rc != 0:
            return ResumeWorkflowResponse(
                run_id="",
                status="failed",
            )

        response = _parse_resume_response(stdout)
        if response is None:
            return ResumeWorkflowResponse(
                run_id="",
                status="failed",
            )

        return response

    async def reject(self, request: ResumeWorkflowRequest) -> ResumeWorkflowResponse:
        workflow_run_id = str(request.workflow_run_id)
        node_id = getattr(request, "node_id", None)

        if not node_id or request.comment is None:
            return ResumeWorkflowResponse(
                run_id="",
                status="failed",
            )

        cli_args = [
            "workflow",
            "review",
            "--run-id",
            workflow_run_id,
            "--node-id",
            node_id,
            "--reject",
            "--comment",
            request.comment,
            "--json",
            "--yes",
        ]

        rc, stdout, _stderr = await self._exec_cmd(cli_args)
        if rc != 0:
            return ResumeWorkflowResponse(
                run_id="",
                status="failed",
            )

        response = _parse_resume_response(stdout)
        if response is None:
            return ResumeWorkflowResponse(
                run_id="",
                status="failed",
            )

        return response
