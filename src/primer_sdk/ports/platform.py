"""Platform port interfaces for the Primer SDK.

These ABCs represent EXISTING platform capabilities that SDK consumers
INVOKE — they do NOT implement these. Concrete implementations are provided by
the platform runtime and injected at execution time.

Usage pattern::

    async def my_agent(run_port: RunWorkflowPort) -> None:
        request = RunWorkflowRequest(
            workflow_id=my_workflow_id,
            thread_id='thread-123',
            input_data={'key': 'value'},
            org_id=None,
        )
        async for event in run_port.run(request):
            handle(event)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from primer_sdk.events import AGUIEvent


class RunWorkflowRequest:
    """Request to start a new workflow run.

    Args:
        workflow_id: UUID of the workflow definition to execute.
        thread_id: Conversation/session thread identifier.
        input_data: Optional key-value payload passed as workflow input.
        org_id: Optional organisation scoping override; defaults to the
            caller's organisation when ``None``.
    """

    def __init__(
        self,
        workflow_id: UUID,
        thread_id: str,
        input_data: dict | None,
        org_id: UUID | None,
    ) -> None:
        self.workflow_id = workflow_id
        self.thread_id = thread_id
        self.input_data = input_data
        self.org_id = org_id


class RunWorkflowResponse:
    """Response from a synchronous workflow run.

    Args:
        run_id: Unique identifier for the completed run.
        output: Final output produced by the workflow.
        status: Terminal status string (e.g. ``'completed'``, ``'failed'``).
    """

    def __init__(self, run_id: str, output: dict, status: str) -> None:
        self.run_id = run_id
        self.output = output
        self.status = status


class ResumeWorkflowRequest:
    """Request to resume a paused (human-in-the-loop) workflow run.

    Args:
        workflow_run_id: UUID of the paused workflow run to resume.
        thread_id: Conversation/session thread identifier.
        decision: Human approval decision (e.g. ``'approve'``, ``'reject'``).
        input_data: Optional additional data to inject on resume.
        comment: Optional free-text comment attached to the decision.
    """

    def __init__(
        self,
        workflow_run_id: UUID,
        thread_id: str,
        decision: str | None,
        input_data: dict | None,
        comment: str | None,
    ) -> None:
        self.workflow_run_id = workflow_run_id
        self.thread_id = thread_id
        self.decision = decision
        self.input_data = input_data
        self.comment = comment


class ResumeWorkflowResponse:
    """Response from a synchronous workflow resume or reject operation.

    Args:
        run_id: Unique identifier for the resumed/rejected run.
        status: Terminal status string (e.g. ``'completed'``, ``'rejected'``).
    """

    def __init__(self, run_id: str, status: str) -> None:
        self.run_id = run_id
        self.status = status


class RunWorkflowPort(ABC):
    """Port for starting new workflow runs.

    This is an EXISTING platform capability — participants call it, they do not
    implement it. The platform injects a concrete implementation at runtime.
    """

    @abstractmethod
    async def run(self, request: RunWorkflowRequest) -> AsyncIterator[AGUIEvent]:
        """Start a workflow and stream AG-UI events as they are produced.

        Args:
            request: Parameters for the new workflow run.

        Yields:
            :class:`~primer_sdk.events.AGUIEvent` instances in emission order.
        """
        ...

    @abstractmethod
    async def run_sync(self, request: RunWorkflowRequest) -> RunWorkflowResponse:
        """Start a workflow and wait for it to complete, returning the final result.

        Args:
            request: Parameters for the new workflow run.

        Returns:
            :class:`RunWorkflowResponse` containing the run id, output, and status.
        """
        ...


class ResumeWorkflowPort(ABC):
    """Port for resuming or rejecting paused (human-in-the-loop) workflow runs.

    This is an EXISTING platform capability — participants call it, they do not
    implement it. The platform injects a concrete implementation at runtime.
    """

    @abstractmethod
    async def resume(self, request: ResumeWorkflowRequest) -> AsyncIterator[AGUIEvent]:
        """Resume a paused workflow and stream AG-UI events as they are produced.

        Args:
            request: Parameters identifying the run to resume.

        Yields:
            :class:`~primer_sdk.events.AGUIEvent` instances in emission order.
        """
        ...

    @abstractmethod
    async def resume_sync(self, request: ResumeWorkflowRequest) -> ResumeWorkflowResponse:
        """Resume a paused workflow and wait for it to complete.

        Args:
            request: Parameters identifying the run to resume.

        Returns:
            :class:`ResumeWorkflowResponse` containing the run id and terminal status.
        """
        ...

    @abstractmethod
    async def reject(self, request: ResumeWorkflowRequest) -> ResumeWorkflowResponse:
        """Reject a paused workflow, cancelling further execution.

        Args:
            request: Parameters identifying the run to reject.

        Returns:
            :class:`ResumeWorkflowResponse` containing the run id and rejection status.
        """
        ...


class EventStreamPort(ABC):
    """Port for serialising and forwarding AG-UI events to downstream consumers.

    This is an EXISTING platform capability — participants call it, they do not
    implement it. The platform injects a concrete implementation at runtime.
    """

    @abstractmethod
    async def stream_events(self, events: AsyncIterator[AGUIEvent]) -> AsyncIterator[str]:
        """Serialise a stream of AG-UI events to Server-Sent Event strings.

        Args:
            events: Async iterator of :class:`~primer_sdk.events.AGUIEvent` objects.

        Yields:
            SSE-formatted strings ready for HTTP streaming responses.
        """
        ...

    @abstractmethod
    async def send_event(self, event: AGUIEvent) -> str:
        """Serialise a single AG-UI event to an SSE-formatted string.

        Args:
            event: The :class:`~primer_sdk.events.AGUIEvent` to serialise.

        Returns:
            SSE-formatted string for the given event.
        """
        ...

    @abstractmethod
    async def send_error(self, error: Exception, thread_id: str, run_id: str) -> str:
        """Serialise an error condition as an SSE-formatted error event.

        Args:
            error: The exception to report.
            thread_id: Thread/session identifier for context.
            run_id: Run identifier for context.

        Returns:
            SSE-formatted error event string.
        """
        ...


class StateManagerPort(ABC):
    """Port for reading and mutating per-thread workflow state.

    This is an EXISTING platform capability — participants call it, they do not
    implement it. The platform injects a concrete implementation at runtime.
    """

    @abstractmethod
    async def get_state(self, thread_id: str) -> dict[str, Any]:
        """Retrieve the current state snapshot for a thread.

        Args:
            thread_id: The thread whose state should be fetched.

        Returns:
            A dictionary containing the current state key-value pairs.
        """
        ...

    @abstractmethod
    async def update_state(self, thread_id: str, state: dict[str, Any]) -> None:
        """Replace the state for a thread with a new snapshot.

        Args:
            thread_id: The thread whose state should be replaced.
            state: The new state dictionary to persist.
        """
        ...

    @abstractmethod
    async def apply_delta(self, thread_id: str, delta: list[dict[str, Any]]) -> None:
        """Apply a JSON Patch delta to the current state of a thread.

        Args:
            thread_id: The thread whose state should be patched.
            delta: A list of JSON Patch operation objects
                (RFC 6902, e.g. ``[{'op': 'replace', 'path': '/key', 'value': 1}]``).
        """
        ...
