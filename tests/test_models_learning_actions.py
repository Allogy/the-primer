from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from primer_sdk.models.learning_actions import (
    AgentLoopDefinition,
    ExitCondition,
    # Layer 3 — Agent Loops
    GoalEvaluator,
    LoopEvent,
    LoopIteration,
    OrchestrationEdge,
    OrchestrationEvent,
    OrchestrationPlan,
    OrchestrationRun,
    OrchestrationStatus,
    OrchestrationStep,
    # Layer 2 — Orchestrators
    RetryConfig,
    TriggerDefinition,
    TriggerEvent,
    # Layer 1 — Triggers
    TriggerTarget,
    WorkflowResult,
)

# ---------------------------------------------------------------------------
# Layer 1 — Triggers
# ---------------------------------------------------------------------------


class TestTriggerTarget:
    def test_basic_creation(self):
        target = TriggerTarget(target_type="workflow", target_id=uuid4())
        assert target.target_type == "workflow"
        assert isinstance(target.target_id, UUID)
        assert target.initial_input is None

    def test_with_initial_input(self):
        target = TriggerTarget(
            target_type="agent",
            target_id=uuid4(),
            initial_input={"key": "value", "count": 3},
        )
        assert target.initial_input == {"key": "value", "count": 3}

    def test_initial_input_defaults_to_none(self):
        target = TriggerTarget(target_type="workflow", target_id=uuid4())
        assert target.initial_input is None


class TestTriggerDefinitionCronTrigger:
    def test_cron_trigger_creation(self):
        target = TriggerTarget(target_type="workflow", target_id=uuid4())
        trig = TriggerDefinition(
            id=uuid4(),
            org_id=uuid4(),
            name="nightly-report",
            trigger_type="cron",
            config={"schedule": "0 2 * * *"},
            target=target,
            enabled=True,
        )
        assert trig.trigger_type == "cron"
        assert trig.config == {"schedule": "0 2 * * *"}
        assert trig.enabled is True
        assert isinstance(trig.created_at, datetime)
        assert trig.last_fired is None
        assert trig.fire_count == 0

    def test_cron_trigger_defaults(self):
        target = TriggerTarget(target_type="workflow", target_id=uuid4())
        trig = TriggerDefinition(
            id=uuid4(),
            org_id=uuid4(),
            name="test-cron",
            trigger_type="cron",
            config={"schedule": "*/5 * * * *"},
            target=target,
            enabled=False,
        )
        assert trig.fire_count == 0
        assert trig.last_fired is None

    def test_cron_trigger_with_last_fired(self):
        fired_at = datetime.now(tz=timezone.utc)
        target = TriggerTarget(target_type="workflow", target_id=uuid4())
        trig = TriggerDefinition(
            id=uuid4(),
            org_id=uuid4(),
            name="test",
            trigger_type="cron",
            config={},
            target=target,
            enabled=True,
            last_fired=fired_at,
            fire_count=5,
        )
        assert trig.last_fired == fired_at
        assert trig.fire_count == 5


class TestTriggerDefinitionWebhookTrigger:
    def test_webhook_trigger_creation(self):
        target = TriggerTarget(target_type="agent", target_id=uuid4())
        trig = TriggerDefinition(
            id=uuid4(),
            org_id=uuid4(),
            name="github-push",
            trigger_type="webhook",
            config={"secret": "abc123", "events": ["push", "pull_request"]},
            target=target,
            enabled=True,
        )
        assert trig.trigger_type == "webhook"
        assert trig.config["events"] == ["push", "pull_request"]

    def test_trigger_ids_are_uuids(self):
        target = TriggerTarget(target_type="workflow", target_id=uuid4())
        trig = TriggerDefinition(
            id=uuid4(),
            org_id=uuid4(),
            name="test",
            trigger_type="webhook",
            config={},
            target=target,
            enabled=True,
        )
        assert isinstance(trig.id, UUID)
        assert isinstance(trig.org_id, UUID)


class TestTriggerEvent:
    def test_trigger_event_creation(self):
        target = TriggerTarget(target_type="workflow", target_id=uuid4())
        event = TriggerEvent(
            trigger_id=uuid4(),
            fired_at=datetime.now(tz=timezone.utc),
            target=target,
            result="success",
        )
        assert event.result == "success"
        assert event.error is None
        assert event.run_id is None

    def test_trigger_event_with_error(self):
        target = TriggerTarget(target_type="workflow", target_id=uuid4())
        event = TriggerEvent(
            trigger_id=uuid4(),
            fired_at=datetime.now(tz=timezone.utc),
            target=target,
            result="failure",
            error="connection timeout",
        )
        assert event.error == "connection timeout"

    def test_trigger_event_with_run_id(self):
        run_id = uuid4()
        target = TriggerTarget(target_type="workflow", target_id=uuid4())
        event = TriggerEvent(
            trigger_id=uuid4(),
            fired_at=datetime.now(tz=timezone.utc),
            target=target,
            result="success",
            run_id=run_id,
        )
        assert event.run_id == run_id


# ---------------------------------------------------------------------------
# Layer 2 — Orchestrators
# ---------------------------------------------------------------------------


class TestRetryConfig:
    def test_retry_config_creation(self):
        retry = RetryConfig(
            max_retries=3,
            backoff_seconds=2.5,
            retry_on=["timeout", "rate_limit"],
        )
        assert retry.max_retries == 3
        assert retry.backoff_seconds == 2.5
        assert retry.retry_on == ["timeout", "rate_limit"]

    def test_retry_on_is_list(self):
        retry = RetryConfig(max_retries=1, backoff_seconds=1.0, retry_on=["error"])
        assert isinstance(retry.retry_on, list)


class TestOrchestrationStep:
    def test_minimal_step(self):
        step = OrchestrationStep(slug="fetch-data", step_type="workflow")
        assert step.slug == "fetch-data"
        assert step.step_type == "workflow"
        assert step.target_id is None
        assert step.input_mapping == {}
        assert step.output_mapping == {}
        assert step.retry is None

    def test_step_with_all_fields(self):
        retry = RetryConfig(max_retries=2, backoff_seconds=1.0, retry_on=["timeout"])
        step = OrchestrationStep(
            slug="process",
            step_type="agent",
            target_id=uuid4(),
            input_mapping={"data": "$.fetch.result"},
            output_mapping={"result": "$.output"},
            retry=retry,
        )
        assert step.input_mapping == {"data": "$.fetch.result"}
        assert step.retry is not None
        assert step.retry.max_retries == 2

    def test_mutable_defaults_independent(self):
        step1 = OrchestrationStep(slug="a", step_type="workflow")
        step2 = OrchestrationStep(slug="b", step_type="workflow")
        step1.input_mapping["key"] = "val"
        assert step2.input_mapping == {}


class TestOrchestrationEdge:
    def test_edge_creation(self):
        edge = OrchestrationEdge(from_step="step-a", to_step="step-b")
        assert edge.from_step == "step-a"
        assert edge.to_step == "step-b"
        assert edge.condition is None

    def test_edge_with_condition(self):
        edge = OrchestrationEdge(
            from_step="check",
            to_step="notify",
            condition='$.output.status == "success"',
        )
        assert edge.condition == '$.output.status == "success"'


class TestOrchestrationPlanSequential:
    def _make_plan(self, **kwargs):
        steps = [
            OrchestrationStep(slug="step-1", step_type="workflow"),
            OrchestrationStep(slug="step-2", step_type="agent"),
        ]
        edges = [OrchestrationEdge(from_step="step-1", to_step="step-2")]
        defaults = dict(
            id=uuid4(),
            org_id=uuid4(),
            name="sequential-plan",
            description="A sequential plan",
            steps=steps,
            edges=edges,
            entry_step="step-1",
            error_strategy="fail_fast",
        )
        defaults.update(kwargs)
        return OrchestrationPlan(**defaults)

    def test_sequential_plan_creation(self):
        plan = self._make_plan()
        assert plan.name == "sequential-plan"
        assert len(plan.steps) == 2
        assert len(plan.edges) == 1
        assert plan.entry_step == "step-1"
        assert plan.error_strategy == "fail_fast"
        assert plan.compensating_steps is None
        assert plan.timeout is None
        assert plan.state == {}

    def test_sequential_plan_ids(self):
        plan = self._make_plan()
        assert isinstance(plan.id, UUID)
        assert isinstance(plan.org_id, UUID)

    def test_plan_state_defaults_to_empty(self):
        plan = self._make_plan()
        assert plan.state == {}

    def test_mutable_state_independent(self):
        plan1 = self._make_plan()
        plan2 = self._make_plan()
        plan1.state["key"] = "val"
        assert plan2.state == {}


class TestOrchestrationPlanWithCompensation:
    def test_plan_with_compensation(self):
        steps = [OrchestrationStep(slug="charge", step_type="workflow")]
        edges: list[OrchestrationEdge] = []
        plan = OrchestrationPlan(
            id=uuid4(),
            org_id=uuid4(),
            name="sagas-plan",
            description="Plan with compensation",
            steps=steps,
            edges=edges,
            entry_step="charge",
            error_strategy="compensate",
            compensating_steps={"charge": "refund"},
            timeout=300,
        )
        assert plan.compensating_steps == {"charge": "refund"}
        assert plan.timeout == 300
        assert plan.error_strategy == "compensate"


class TestOrchestrationEvent:
    def test_minimal_event(self):
        event = OrchestrationEvent(
            event_type="step_started",
            timestamp=datetime.now(tz=timezone.utc),
        )
        assert event.event_type == "step_started"
        assert event.step_slug is None
        assert event.workflow_id is None
        assert event.output is None
        assert event.error is None
        assert event.metadata == {}

    def test_event_with_all_fields(self):
        wf_id = uuid4()
        event = OrchestrationEvent(
            event_type="step_completed",
            timestamp=datetime.now(tz=timezone.utc),
            step_slug="process",
            workflow_id=wf_id,
            output={"result": 42},
            error=None,
            metadata={"source": "test"},
        )
        assert event.step_slug == "process"
        assert event.workflow_id == wf_id
        assert event.output == {"result": 42}
        assert event.metadata == {"source": "test"}

    def test_event_with_error(self):
        event = OrchestrationEvent(
            event_type="step_failed",
            timestamp=datetime.now(tz=timezone.utc),
            error="step timed out",
        )
        assert event.error == "step timed out"

    def test_metadata_mutable_default_independent(self):
        e1 = OrchestrationEvent(event_type="x", timestamp=datetime.now(tz=timezone.utc))
        e2 = OrchestrationEvent(event_type="y", timestamp=datetime.now(tz=timezone.utc))
        e1.metadata["k"] = "v"
        assert e2.metadata == {}


class TestOrchestrationRun:
    def test_run_creation(self):
        run = OrchestrationRun(
            id=uuid4(),
            plan_id=uuid4(),
            org_id=uuid4(),
            status="running",
            started_at=datetime.now(tz=timezone.utc),
        )
        assert run.status == "running"
        assert run.completed_at is None
        assert run.current_step is None
        assert run.completed_steps == []
        assert run.failed_steps == []
        assert run.state == {}
        assert run.error is None

    def test_run_completed(self):
        now = datetime.now(tz=timezone.utc)
        run = OrchestrationRun(
            id=uuid4(),
            plan_id=uuid4(),
            org_id=uuid4(),
            status="completed",
            started_at=now,
            completed_at=now,
            completed_steps=["step-1", "step-2"],
            state={"result": "done"},
        )
        assert run.completed_at == now
        assert run.completed_steps == ["step-1", "step-2"]

    def test_run_failed(self):
        run = OrchestrationRun(
            id=uuid4(),
            plan_id=uuid4(),
            org_id=uuid4(),
            status="failed",
            started_at=datetime.now(tz=timezone.utc),
            failed_steps=["step-1"],
            error="step-1 exceeded retries",
        )
        assert run.status == "failed"
        assert run.error == "step-1 exceeded retries"
        assert run.failed_steps == ["step-1"]

    def test_mutable_defaults_independent(self):
        r1 = OrchestrationRun(
            id=uuid4(),
            plan_id=uuid4(),
            org_id=uuid4(),
            status="running",
            started_at=datetime.now(tz=timezone.utc),
        )
        r2 = OrchestrationRun(
            id=uuid4(),
            plan_id=uuid4(),
            org_id=uuid4(),
            status="running",
            started_at=datetime.now(tz=timezone.utc),
        )
        r1.completed_steps.append("step-1")
        assert r2.completed_steps == []


class TestOrchestrationStatus:
    def test_status_creation(self):
        status = OrchestrationStatus(
            run_id=uuid4(),
            status="running",
            progress="1/3 steps completed",
            elapsed_seconds=12.5,
        )
        assert status.status == "running"
        assert status.current_step is None
        assert status.elapsed_seconds == 12.5

    def test_status_with_current_step(self):
        status = OrchestrationStatus(
            run_id=uuid4(),
            status="running",
            progress="2/3",
            current_step="process",
            elapsed_seconds=30.0,
        )
        assert status.current_step == "process"


class TestWorkflowResult:
    def test_workflow_result_creation(self):
        result = WorkflowResult(
            run_id=uuid4(),
            workflow_id=uuid4(),
            status="completed",
            output={"answer": 42},
            duration_seconds=5.3,
        )
        assert result.status == "completed"
        assert result.output == {"answer": 42}
        assert result.error is None

    def test_workflow_result_with_error(self):
        result = WorkflowResult(
            run_id=uuid4(),
            workflow_id=uuid4(),
            status="failed",
            output={},
            duration_seconds=1.2,
            error="workflow timed out",
        )
        assert result.error == "workflow timed out"


# ---------------------------------------------------------------------------
# Layer 3 — Agent Loops
# ---------------------------------------------------------------------------


class TestGoalEvaluator:
    def test_creation(self):
        ev = GoalEvaluator(evaluator_type="llm", config={"model": "gpt-4o"})
        assert ev.evaluator_type == "llm"
        assert ev.config == {"model": "gpt-4o"}


class TestExitCondition:
    def test_creation(self):
        cond = ExitCondition(condition_type="score_threshold", config={"threshold": 0.9})
        assert cond.condition_type == "score_threshold"
        assert cond.config == {"threshold": 0.9}


class TestAgentLoopDefinition:
    def _make_loop(self, **kwargs):
        evaluator = GoalEvaluator(evaluator_type="llm", config={})
        defaults = dict(
            id=uuid4(),
            org_id=uuid4(),
            name="research-loop",
            description="Iterative research loop",
            agent_id=uuid4(),
            goal="Summarise the latest AI papers",
            goal_evaluator=evaluator,
            max_iterations=10,
        )
        defaults.update(kwargs)
        return AgentLoopDefinition(**defaults)

    def test_minimal_loop(self):
        loop = self._make_loop()
        assert loop.name == "research-loop"
        assert loop.max_iterations == 10
        assert loop.iteration_timeout is None
        assert loop.cooldown == 0
        assert loop.reflect_prompt is None
        assert loop.reflection_strategy == "self_critique"
        assert loop.accumulate_state is True
        assert loop.state_schema == {}
        assert loop.exit_conditions == []

    def test_loop_with_exit_conditions(self):
        cond = ExitCondition(condition_type="max_tokens", config={"limit": 10000})
        loop = self._make_loop(exit_conditions=[cond])
        assert len(loop.exit_conditions) == 1
        assert loop.exit_conditions[0].condition_type == "max_tokens"

    def test_loop_with_optional_fields(self):
        loop = self._make_loop(
            iteration_timeout=60,
            cooldown=5,
            reflect_prompt="How did I do?",
            reflection_strategy="adversarial",
        )
        assert loop.iteration_timeout == 60
        assert loop.cooldown == 5
        assert loop.reflect_prompt == "How did I do?"
        assert loop.reflection_strategy == "adversarial"

    def test_mutable_defaults_independent(self):
        loop1 = self._make_loop()
        loop2 = self._make_loop()
        loop1.exit_conditions.append(ExitCondition(condition_type="x", config={}))
        assert loop2.exit_conditions == []


class TestLoopEvent:
    def test_minimal_loop_event(self):
        event = LoopEvent(
            event_type="iteration_started",
            timestamp=datetime.now(tz=timezone.utc),
            iteration_num=1,
        )
        assert event.event_type == "iteration_started"
        assert event.iteration_num == 1
        assert event.output is None
        assert event.reflection is None
        assert event.goal_score is None
        assert event.goal_met is None
        assert event.final_state is None
        assert event.reason is None

    def test_loop_event_with_all_fields(self):
        event = LoopEvent(
            event_type="iteration_completed",
            timestamp=datetime.now(tz=timezone.utc),
            iteration_num=3,
            output={"summary": "done"},
            reflection="I did well",
            goal_score=0.87,
            goal_met=False,
            final_state={"progress": "87%"},
            reason="continuing",
        )
        assert event.goal_score == pytest.approx(0.87)
        assert event.goal_met is False

    def test_loop_event_goal_met(self):
        event = LoopEvent(
            event_type="loop_finished",
            timestamp=datetime.now(tz=timezone.utc),
            iteration_num=5,
            goal_score=0.95,
            goal_met=True,
            reason="goal achieved",
        )
        assert event.goal_met is True
        assert event.reason == "goal achieved"


class TestLoopIteration:
    def test_creation(self):
        now = datetime.now(tz=timezone.utc)
        iteration = LoopIteration(
            iteration_num=1,
            started_at=now,
            completed_at=now,
            input_context={"query": "find info"},
            output={"result": "found it"},
        )
        assert iteration.iteration_num == 1
        assert iteration.reflection is None
        assert iteration.goal_score is None
        assert iteration.goal_met is False
        assert iteration.tokens_used is None

    def test_with_all_fields(self):
        now = datetime.now(tz=timezone.utc)
        iteration = LoopIteration(
            iteration_num=2,
            started_at=now,
            completed_at=now,
            input_context={"ctx": "data"},
            output={"answer": 42},
            reflection="Good result",
            goal_score=0.9,
            goal_met=True,
            tokens_used=1500,
        )
        assert iteration.goal_met is True
        assert iteration.tokens_used == 1500
        assert iteration.goal_score == pytest.approx(0.9)
