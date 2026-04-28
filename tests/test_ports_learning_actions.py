from __future__ import annotations

from uuid import uuid4

import pytest

from primer_sdk.ports.learning_actions import (
    LoopStatePort,
    OrchestrationStatePort,
    RegisterTriggerPort,
    RunAgentLoopPort,
    RunOrchestratorPort,
    TriggerSchedulerPort,
    WorkflowInvokerPort,
)

# ---------------------------------------------------------------------------
# ABC instantiation tests
# ---------------------------------------------------------------------------


class TestRegisterTriggerPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            RegisterTriggerPort()  # type: ignore[abstract]


class TestRunOrchestratorPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            RunOrchestratorPort()  # type: ignore[abstract]


class TestRunAgentLoopPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            RunAgentLoopPort()  # type: ignore[abstract]


class TestTriggerSchedulerPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            TriggerSchedulerPort()  # type: ignore[abstract]


class TestWorkflowInvokerPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            WorkflowInvokerPort()  # type: ignore[abstract]


class TestLoopStatePortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            LoopStatePort()  # type: ignore[abstract]


class TestOrchestrationStatePortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            OrchestrationStatePort()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Concrete implementation tests
# ---------------------------------------------------------------------------


class ConcreteRegisterTriggerPort(RegisterTriggerPort):
    async def register(self, trigger):
        return uuid4()

    async def update(self, trigger_id, updates):
        from primer_sdk.models.learning_actions import TriggerDefinition, TriggerTarget

        return TriggerDefinition(
            id=trigger_id,
            org_id=uuid4(),
            name="test",
            trigger_type="cron",
            config={},
            target=TriggerTarget(target_type="workflow", target_id=uuid4()),
            enabled=True,
        )

    async def cancel(self, trigger_id):
        return None

    async def list_triggers(self, org_id):
        return []

    async def get_trigger_history(self, trigger_id, limit):
        return []


class TestConcreteRegisterTriggerPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteRegisterTriggerPort()
        assert isinstance(port, RegisterTriggerPort)


class ConcreteRunOrchestratorPort(RunOrchestratorPort):
    async def run(self, plan, initial_input=None):
        return
        yield  # make it an async generator

    async def cancel(self, orchestration_run_id):
        return None

    async def get_status(self, orchestration_run_id):
        from primer_sdk.models.learning_actions import OrchestrationStatus

        return OrchestrationStatus(
            run_id=orchestration_run_id,
            status="running",
            progress="0/1",
            elapsed_seconds=0.0,
        )


class TestConcreteRunOrchestratorPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteRunOrchestratorPort()
        assert isinstance(port, RunOrchestratorPort)


class ConcreteRunAgentLoopPort(RunAgentLoopPort):
    async def run(self, loop_def, initial_context=None):
        return
        yield  # make it an async generator

    async def interrupt(self, loop_run_id):
        return None

    async def inject_feedback(self, loop_run_id, feedback):
        return None


class TestConcreteRunAgentLoopPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteRunAgentLoopPort()
        assert isinstance(port, RunAgentLoopPort)


class ConcreteTriggerSchedulerPort(TriggerSchedulerPort):
    async def schedule(self, trigger):
        return "handle-123"

    async def cancel(self, handle):
        return None

    async def list_active(self):
        return []

    async def register_webhook_handler(self, path, callback):
        return None


class TestConcreteTriggerSchedulerPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteTriggerSchedulerPort()
        assert isinstance(port, TriggerSchedulerPort)


class ConcreteWorkflowInvokerPort(WorkflowInvokerPort):
    async def invoke(self, workflow_id, input_data, timeout=None):
        from primer_sdk.models.learning_actions import WorkflowResult

        return WorkflowResult(
            run_id=uuid4(),
            workflow_id=workflow_id,
            status="completed",
            output={},
            duration_seconds=0.0,
        )

    async def invoke_streaming(self, workflow_id, input_data):
        return
        yield  # make it an async generator


class TestConcreteWorkflowInvokerPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteWorkflowInvokerPort()
        assert isinstance(port, WorkflowInvokerPort)


class ConcreteLoopStatePort(LoopStatePort):
    async def save_iteration(self, loop_run_id, iteration):
        return None

    async def get_iterations(self, loop_run_id):
        return []

    async def save_accumulated_state(self, loop_run_id, state):
        return None

    async def get_accumulated_state(self, loop_run_id):
        return {}


class TestConcreteLoopStatePort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteLoopStatePort()
        assert isinstance(port, LoopStatePort)


class ConcreteOrchestrationStatePort(OrchestrationStatePort):
    async def save_run(self, run):
        return None

    async def get_run(self, run_id):
        return None

    async def list_runs(self, org_id, plan_id=None):
        return []


class TestConcreteOrchestrationStatePort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteOrchestrationStatePort()
        assert isinstance(port, OrchestrationStatePort)
