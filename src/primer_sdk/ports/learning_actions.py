"""Learning Actions ports — triggers, orchestration, and agent loops."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from primer_sdk.events import AGUIEvent
from primer_sdk.models.learning_actions import (
    AgentLoopDefinition,
    LoopEvent,
    LoopIteration,
    OrchestrationEvent,
    OrchestrationPlan,
    OrchestrationRun,
    OrchestrationStatus,
    TriggerDefinition,
    TriggerEvent,
    WorkflowResult,
)

# ---------------------------------------------------------------------------
# Inbound ports
# ---------------------------------------------------------------------------


class RegisterTriggerPort(ABC):
    """Inbound port for registering and managing workflow triggers."""

    @abstractmethod
    async def register(self, trigger: TriggerDefinition) -> UUID:
        """Register a new trigger definition.

        Args:
            trigger: The trigger definition to register.

        Returns:
            UUID of the newly registered trigger.
        """
        ...

    @abstractmethod
    async def update(self, trigger_id: UUID, updates: dict[str, Any]) -> TriggerDefinition:
        """Update an existing trigger definition.

        Args:
            trigger_id: ID of the trigger to update.
            updates: Partial update payload.

        Returns:
            The updated :class:`~primer_sdk.models.learning_actions.TriggerDefinition`.
        """
        ...

    @abstractmethod
    async def cancel(self, trigger_id: UUID) -> None:
        """Cancel (disable/remove) a trigger.

        Args:
            trigger_id: ID of the trigger to cancel.
        """
        ...

    @abstractmethod
    async def list_triggers(self, org_id: UUID) -> list[TriggerDefinition]:
        """List all triggers belonging to an organisation.

        Args:
            org_id: The organisation to query.

        Returns:
            List of :class:`~primer_sdk.models.learning_actions.TriggerDefinition` instances.
        """
        ...

    @abstractmethod
    async def get_trigger_history(self, trigger_id: UUID, limit: int) -> list[TriggerEvent]:
        """Return the firing history for a trigger.

        Args:
            trigger_id: ID of the trigger to inspect.
            limit: Maximum number of history records to return.

        Returns:
            List of :class:`~primer_sdk.models.learning_actions.TriggerEvent` instances.
        """
        ...


class RunOrchestratorPort(ABC):
    """Inbound port for running and managing orchestration plans."""

    @abstractmethod
    async def run(
        self,
        plan: OrchestrationPlan,
        initial_input: dict[str, Any] | None = None,
    ) -> AsyncIterator[OrchestrationEvent]:
        """Execute an orchestration plan and stream events.

        Args:
            plan: The orchestration plan to execute.
            initial_input: Optional initial state to seed the run.

        Yields:
            :class:`~primer_sdk.models.learning_actions.OrchestrationEvent` instances.
        """
        ...

    @abstractmethod
    async def cancel(self, orchestration_run_id: UUID) -> None:
        """Cancel a running orchestration.

        Args:
            orchestration_run_id: ID of the run to cancel.
        """
        ...

    @abstractmethod
    async def get_status(self, orchestration_run_id: UUID) -> OrchestrationStatus:
        """Retrieve the current status of an orchestration run.

        Args:
            orchestration_run_id: ID of the run to inspect.

        Returns:
            :class:`~primer_sdk.models.learning_actions.OrchestrationStatus` snapshot.
        """
        ...


class RunAgentLoopPort(ABC):
    """Inbound port for running and managing agent loops."""

    @abstractmethod
    async def run(
        self,
        loop_def: AgentLoopDefinition,
        initial_context: dict[str, Any] | None = None,
    ) -> AsyncIterator[LoopEvent]:
        """Execute an agent loop and stream loop events.

        Args:
            loop_def: The agent loop definition to execute.
            initial_context: Optional context to inject at the first iteration.

        Yields:
            :class:`~primer_sdk.models.learning_actions.LoopEvent` instances.
        """
        ...

    @abstractmethod
    async def interrupt(self, loop_run_id: UUID) -> None:
        """Interrupt a running agent loop.

        Args:
            loop_run_id: ID of the loop run to interrupt.
        """
        ...

    @abstractmethod
    async def inject_feedback(self, loop_run_id: UUID, feedback: dict[str, Any]) -> None:
        """Inject external feedback into a running agent loop.

        Args:
            loop_run_id: ID of the loop run to inject feedback into.
            feedback: Feedback payload to inject.
        """
        ...


# ---------------------------------------------------------------------------
# Outbound ports
# ---------------------------------------------------------------------------


class TriggerSchedulerPort(ABC):
    """Outbound port for scheduling triggers via an external scheduler."""

    @abstractmethod
    async def schedule(self, trigger: TriggerDefinition) -> str:
        """Schedule a trigger and return a scheduler handle.

        Args:
            trigger: The trigger definition to schedule.

        Returns:
            Opaque handle string identifying the scheduled job.
        """
        ...

    @abstractmethod
    async def cancel(self, handle: str) -> None:
        """Cancel a scheduled trigger by handle.

        Args:
            handle: The scheduler handle returned by :meth:`schedule`.
        """
        ...

    @abstractmethod
    async def list_active(self) -> list[dict[str, Any]]:
        """List all currently active scheduled triggers.

        Returns:
            List of scheduler-specific metadata dictionaries.
        """
        ...

    @abstractmethod
    async def register_webhook_handler(self, path: str, callback: Any) -> None:
        """Register a callback for an inbound webhook path.

        Args:
            path: The URL path to listen on.
            callback: Callable invoked when a request arrives at ``path``.
        """
        ...


class WorkflowInvokerPort(ABC):
    """Outbound port for invoking platform workflows."""

    @abstractmethod
    async def invoke(
        self,
        workflow_id: UUID,
        input_data: dict[str, Any],
        timeout: int | None = None,
    ) -> WorkflowResult:
        """Invoke a workflow synchronously and wait for the result.

        Args:
            workflow_id: UUID of the workflow to invoke.
            input_data: Input payload for the workflow.
            timeout: Optional timeout in seconds.

        Returns:
            :class:`~primer_sdk.models.learning_actions.WorkflowResult`.
        """
        ...

    @abstractmethod
    async def invoke_streaming(
        self,
        workflow_id: UUID,
        input_data: dict[str, Any],
    ) -> AsyncIterator[AGUIEvent]:
        """Invoke a workflow and stream AG-UI events as they are produced.

        Args:
            workflow_id: UUID of the workflow to invoke.
            input_data: Input payload for the workflow.

        Yields:
            :class:`~primer_sdk.events.AGUIEvent` instances.
        """
        ...


class LoopStatePort(ABC):
    """Outbound port for persisting agent loop run state."""

    @abstractmethod
    async def save_iteration(self, loop_run_id: UUID, iteration: LoopIteration) -> None:
        """Persist a completed loop iteration.

        Args:
            loop_run_id: ID of the loop run this iteration belongs to.
            iteration: The iteration record to persist.
        """
        ...

    @abstractmethod
    async def get_iterations(self, loop_run_id: UUID) -> list[LoopIteration]:
        """Retrieve all recorded iterations for a loop run.

        Args:
            loop_run_id: ID of the loop run to query.

        Returns:
            List of :class:`~primer_sdk.models.learning_actions.LoopIteration` instances.
        """
        ...

    @abstractmethod
    async def save_accumulated_state(self, loop_run_id: UUID, state: dict[str, Any]) -> None:
        """Persist the accumulated state for a loop run.

        Args:
            loop_run_id: ID of the loop run.
            state: The accumulated state dictionary to persist.
        """
        ...

    @abstractmethod
    async def get_accumulated_state(self, loop_run_id: UUID) -> dict[str, Any]:
        """Retrieve the accumulated state for a loop run.

        Args:
            loop_run_id: ID of the loop run.

        Returns:
            The accumulated state dictionary.
        """
        ...


class OrchestrationStatePort(ABC):
    """Outbound port for persisting orchestration run state."""

    @abstractmethod
    async def save_run(self, run: OrchestrationRun) -> None:
        """Persist (insert or update) an orchestration run.

        Args:
            run: The orchestration run to save.
        """
        ...

    @abstractmethod
    async def get_run(self, run_id: UUID) -> OrchestrationRun | None:
        """Retrieve an orchestration run by ID, or ``None`` if not found.

        Args:
            run_id: ID of the run to retrieve.

        Returns:
            The :class:`~primer_sdk.models.learning_actions.OrchestrationRun` or ``None``.
        """
        ...

    @abstractmethod
    async def list_runs(
        self,
        org_id: UUID,
        plan_id: UUID | None = None,
    ) -> list[OrchestrationRun]:
        """List orchestration runs for an organisation, optionally filtered by plan.

        Args:
            org_id: The organisation to query.
            plan_id: Optional plan ID to filter results.

        Returns:
            List of :class:`~primer_sdk.models.learning_actions.OrchestrationRun` instances.
        """
        ...
