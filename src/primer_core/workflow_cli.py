"""Adapters from workflow-cli-style clients to Capillary workflow ports."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, Protocol
from uuid import UUID

from capillary_actions_sdk.events import (
    AGUIEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
)
from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)


class WorkflowClientInstance(Protocol):
    """Subset of workflow-cli's WorkflowClient needed by the run port adapter."""

    def start_workflow_temporal(
        self,
        workflow_id: str | UUID,
        inputs: dict[str, Any] | None = None,
    ) -> Any:
        """Start a workflow run and return an object with a run_id attribute."""
        ...

    def get_workflow_status(self, workflow_id: str | UUID, run_id: str) -> Any:
        """Return an object with status/current_node/state attributes."""
        ...


class WorkflowInputClientInstance(WorkflowClientInstance, Protocol):
    """Optional workflow-cli client capability for headless INPUT-node submission."""

    def submit_input(
        self,
        workflow_id: str | UUID,
        *,
        run_id: str,
        node_id: str,
        input_data: dict[str, Any],
    ) -> Any:
        """Submit input data to a paused INPUT node."""
        ...


_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT", "TIMEOUT"}
_FAILURE_STATUSES = {"FAILED", "CANCELLED", "TIMED_OUT", "TIMEOUT"}
_HITL_STATUSES = {"WAITING_FOR_INPUT", "WAITING_FOR_REVIEW"}
_logger = logging.getLogger(__name__)


class RunWorkflowClientPort(RunWorkflowPort):
    """RunWorkflowPort backed by a workflow-cli-compatible client instance.

    This adapter lets Primer depend on the SDK's platform port while using the
    existing workflow-cli client class as the concrete runner in local tools,
    automation, or service wiring.
    """

    def __init__(
        self,
        client: WorkflowClientInstance,
        *,
        poll_interval_seconds: float = 2.0,
        max_poll_seconds: float = 300.0,
    ) -> None:
        self.client = client
        self.poll_interval_seconds = poll_interval_seconds
        self.max_poll_seconds = max_poll_seconds

    async def run(self, request: RunWorkflowRequest) -> AsyncIterator[AGUIEvent]:
        """Start a workflow and yield coarse AG-UI lifecycle events."""
        start_response = await self._start(request)
        run_id = str(start_response.run_id)

        yield RunStartedEvent(thread_id=request.thread_id, run_id=run_id)

        response = await self._poll_until_done(request, run_id)
        if response.status.upper() in _HITL_STATUSES:
            yield RunErrorEvent(
                thread_id=request.thread_id,
                run_id=run_id,
                error=f"Workflow paused with status {response.status}",
                code=response.status,
            )
            return

        if response.status.upper() in _FAILURE_STATUSES:
            yield RunErrorEvent(
                thread_id=request.thread_id,
                run_id=run_id,
                error=f"Workflow finished with status {response.status}",
                code=response.status,
            )
            return

        yield RunFinishedEvent(thread_id=request.thread_id, run_id=run_id)

    async def run_sync(self, request: RunWorkflowRequest) -> RunWorkflowResponse:
        """Start a workflow through the wrapped client and poll until done."""
        start_response = await self._start(request)
        return await self._poll_until_done(request, str(start_response.run_id))

    async def _start(self, request: RunWorkflowRequest) -> Any:
        return await asyncio.to_thread(
            self.client.start_workflow_temporal,
            request.workflow_id,
            inputs=request.input_data or {},
        )

    async def _poll_until_done(
        self,
        request: RunWorkflowRequest,
        run_id: str,
    ) -> RunWorkflowResponse:
        deadline = asyncio.get_running_loop().time() + self.max_poll_seconds
        submitted_initial_input = False
        submitted_input_node_id: str | None = None

        while True:
            status_response = await asyncio.to_thread(
                self.client.get_workflow_status,
                request.workflow_id,
                run_id,
            )
            status = _status(status_response)

            if (
                status == "WAITING_FOR_INPUT"
                and request.input_data
                and not submitted_initial_input
                and _supports_submit_input(self.client)
            ):
                node_id = _waiting_input_node_id(status_response)
                if node_id:
                    submitted_initial_input = True
                    try:
                        await asyncio.to_thread(
                            self.client.submit_input,
                            request.workflow_id,
                            run_id=run_id,
                            node_id=node_id,
                            input_data=request.input_data,
                        )
                    except Exception as exc:
                        _logger.warning(
                            "Failed to submit workflow input for run %s node %s",
                            run_id,
                            node_id,
                            exc_info=exc,
                        )
                    else:
                        submitted_input_node_id = node_id
                        await asyncio.sleep(self.poll_interval_seconds)
                        continue

            if status in _TERMINAL_STATUSES:
                return RunWorkflowResponse(
                    run_id=run_id,
                    output=_output(status_response),
                    status=status,
                )

            if status == "WAITING_FOR_INPUT":
                node_id = _waiting_input_node_id(status_response)
                if submitted_input_node_id and node_id == submitted_input_node_id:
                    if asyncio.get_running_loop().time() >= deadline:
                        return RunWorkflowResponse(
                            run_id=run_id,
                            output=_output(status_response),
                            status="TIMED_OUT",
                        )

                    await asyncio.sleep(self.poll_interval_seconds)
                    continue

                return RunWorkflowResponse(
                    run_id=run_id,
                    output=_output(status_response),
                    status=status,
                )

            if status in _HITL_STATUSES:
                return RunWorkflowResponse(
                    run_id=run_id,
                    output=_output(status_response),
                    status=status,
                )

            if asyncio.get_running_loop().time() >= deadline:
                return RunWorkflowResponse(
                    run_id=run_id,
                    output=_output(status_response),
                    status="TIMED_OUT",
                )

            await asyncio.sleep(self.poll_interval_seconds)


def _status(status_response: Any) -> str:
    status = str(getattr(status_response, "status", "UNKNOWN")).upper()
    state = getattr(status_response, "state", {}) or {}
    execution_status = state.get("execution_status")
    if status == "RUNNING" and execution_status:
        return str(execution_status).upper()
    return status


def _output(status_response: Any) -> dict[str, Any]:
    state = getattr(status_response, "state", {}) or {}
    return {
        "node_outputs": state.get("node_outputs", {}) or {},
        "state": state,
    }


def _waiting_input_node_id(status_response: Any) -> str | None:
    state = getattr(status_response, "state", {}) or {}
    node_id = (
        state.get("waiting_for_input_node_id")
        or state.get("waiting_input_node_id")
        or state.get("current_node_id")
    )
    if node_id:
        return str(node_id)

    current_node = getattr(status_response, "current_node", None)
    if current_node:
        return str(current_node)


def _supports_submit_input(client: WorkflowClientInstance) -> bool:
    return callable(getattr(client, "submit_input", None))
