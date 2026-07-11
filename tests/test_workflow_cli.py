"""Tests for workflow-cli client adapters."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from capillary_actions_sdk.events import AGUIEventType
from capillary_actions_sdk.ports.platform import RunWorkflowPort, RunWorkflowRequest

from primer_core.workflow_cli import RunWorkflowClientPort


class RecordingWorkflowClient:
    """Synchronous workflow-cli-shaped client fake."""

    def __init__(
        self,
        statuses: list[SimpleNamespace],
        *,
        submit_error: Exception | None = None,
    ) -> None:
        self.statuses = list(statuses)
        self.submit_error = submit_error
        self.started: list[tuple[object, dict]] = []
        self.submitted_inputs: list[tuple[object, str, str, dict]] = []

    def start_workflow_temporal(self, workflow_id: object, inputs: dict | None = None):
        self.started.append((workflow_id, inputs or {}))
        return SimpleNamespace(run_id="run-123")

    def get_workflow_status(self, workflow_id: object, run_id: str):
        if len(self.statuses) == 1:
            return self.statuses[0]
        return self.statuses.pop(0)

    def submit_input(
        self,
        workflow_id: object,
        *,
        run_id: str,
        node_id: str,
        input_data: dict,
    ) -> None:
        if self.submit_error:
            raise self.submit_error
        self.submitted_inputs.append((workflow_id, run_id, node_id, input_data))


def _request(input_data: dict | None = None) -> RunWorkflowRequest:
    return RunWorkflowRequest(
        workflow_id=uuid4(),
        thread_id="thread-123",
        input_data=input_data,
        org_id=None,
    )


class TestRunWorkflowClientPort:
    async def test_run_sync_starts_and_returns_completed_status(self) -> None:
        client = RecordingWorkflowClient(
            [
                SimpleNamespace(
                    status="COMPLETED",
                    current_node=None,
                    state={"node_outputs": {"result": {"passed": True}}},
                )
            ]
        )
        port = RunWorkflowClientPort(client, poll_interval_seconds=0)
        request = _request({"student_response": "Groups have identity and inverses."})

        assert isinstance(port, RunWorkflowPort)

        response = await port.run_sync(request)

        assert response.run_id == "run-123"
        assert response.status == "COMPLETED"
        assert response.output["node_outputs"] == {"result": {"passed": True}}
        assert client.started == [(request.workflow_id, request.input_data)]

    async def test_run_sync_auto_submits_initial_input_to_first_input_gate(self) -> None:
        client = RecordingWorkflowClient(
            [
                SimpleNamespace(
                    status="WAITING_FOR_INPUT",
                    current_node="input-node",
                    state={"waiting_for_input_node_id": "input-node"},
                ),
                SimpleNamespace(
                    status="COMPLETED",
                    current_node=None,
                    state={"node_outputs": {"result": {"passed": True}}},
                ),
            ]
        )
        port = RunWorkflowClientPort(client, poll_interval_seconds=0)
        request = _request({"student_response": "Associativity is required."})

        response = await port.run_sync(request)

        assert response.status == "COMPLETED"
        assert client.submitted_inputs == [
            (request.workflow_id, "run-123", "input-node", request.input_data)
        ]

    async def test_run_sync_auto_submits_waiting_input_node_id_variant(self) -> None:
        client = RecordingWorkflowClient(
            [
                SimpleNamespace(
                    status="RUNNING",
                    current_node=None,
                    state={
                        "execution_status": "WAITING_FOR_INPUT",
                        "waiting_input_node_id": "input-node",
                    },
                ),
                SimpleNamespace(status="COMPLETED", current_node=None, state={}),
            ]
        )
        port = RunWorkflowClientPort(client, poll_interval_seconds=0)
        request = _request({"student_response": "Associativity is required."})

        response = await port.run_sync(request)

        assert response.status == "COMPLETED"
        assert client.submitted_inputs == [
            (request.workflow_id, "run-123", "input-node", request.input_data)
        ]

    async def test_run_sync_ignores_stale_execution_status_after_completion(self) -> None:
        client = RecordingWorkflowClient(
            [
                SimpleNamespace(
                    status="COMPLETED",
                    current_node=None,
                    state={"execution_status": "RUNNING"},
                )
            ]
        )
        port = RunWorkflowClientPort(client, poll_interval_seconds=0)

        response = await port.run_sync(_request())

        assert response.status == "COMPLETED"

    async def test_run_sync_returns_waiting_status_when_submit_fails(self) -> None:
        client = RecordingWorkflowClient(
            [
                SimpleNamespace(
                    status="WAITING_FOR_INPUT",
                    current_node="input-node",
                    state={},
                )
            ],
            submit_error=RuntimeError("network error"),
        )
        port = RunWorkflowClientPort(client, poll_interval_seconds=0)
        request = _request({"student_response": "Associativity is required."})

        response = await port.run_sync(request)

        assert response.status == "WAITING_FOR_INPUT"

    async def test_run_sync_allows_one_post_submit_waiting_poll(self) -> None:
        client = RecordingWorkflowClient(
            [
                SimpleNamespace(
                    status="WAITING_FOR_INPUT",
                    current_node="input-node",
                    state={},
                ),
                SimpleNamespace(
                    status="WAITING_FOR_INPUT",
                    current_node="input-node",
                    state={},
                ),
                SimpleNamespace(status="COMPLETED", current_node=None, state={}),
            ]
        )
        port = RunWorkflowClientPort(client, poll_interval_seconds=0)

        response = await port.run_sync(_request({"student_response": "answer"}))

        assert response.status == "COMPLETED"

    async def test_run_returns_sdk_lifecycle_events(self) -> None:
        client = RecordingWorkflowClient(
            [SimpleNamespace(status="COMPLETED", current_node=None, state={})]
        )
        port = RunWorkflowClientPort(client, poll_interval_seconds=0)
        request = _request()

        events = [event async for event in port.run(request)]

        assert [event.event_type for event in events] == [
            AGUIEventType.RUN_STARTED,
            AGUIEventType.RUN_FINISHED,
        ]
        assert [event.thread_id for event in events] == ["thread-123", "thread-123"]
        assert [event.run_id for event in events] == ["run-123", "run-123"]

    async def test_run_returns_error_event_for_failed_status(self) -> None:
        client = RecordingWorkflowClient(
            [SimpleNamespace(status="FAILED", current_node=None, state={})]
        )
        port = RunWorkflowClientPort(client, poll_interval_seconds=0)

        events = [event async for event in port.run(_request())]

        assert [event.event_type for event in events] == [
            AGUIEventType.RUN_STARTED,
            AGUIEventType.RUN_ERROR,
        ]

    async def test_run_returns_error_event_for_waiting_status(self) -> None:
        client = RecordingWorkflowClient(
            [SimpleNamespace(status="WAITING_FOR_INPUT", current_node="input-node", state={})]
        )
        port = RunWorkflowClientPort(client, poll_interval_seconds=0)

        events = [event async for event in port.run(_request())]

        assert [event.event_type for event in events] == [
            AGUIEventType.RUN_STARTED,
            AGUIEventType.RUN_ERROR,
        ]
        assert events[-1].code == "WAITING_FOR_INPUT"
