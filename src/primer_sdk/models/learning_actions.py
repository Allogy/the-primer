"""Learning Actions — Engagements & Orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Layer 1 — Triggers
# ---------------------------------------------------------------------------


class TriggerTarget(BaseModel):
    target_type: str
    target_id: UUID
    initial_input: dict[str, Any] | None = None


class TriggerDefinition(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    trigger_type: str
    config: dict[str, Any]
    target: TriggerTarget
    enabled: bool
    created_at: datetime = Field(default_factory=_utcnow)
    last_fired: datetime | None = None
    fire_count: int = 0


class TriggerEvent(BaseModel):
    trigger_id: UUID
    fired_at: datetime
    target: TriggerTarget
    result: str
    error: str | None = None
    run_id: UUID | None = None


# ---------------------------------------------------------------------------
# Layer 2 — Orchestrators
# ---------------------------------------------------------------------------


class RetryConfig(BaseModel):
    max_retries: int
    backoff_seconds: float
    retry_on: list[str]


class OrchestrationStep(BaseModel):
    slug: str
    step_type: str
    target_id: UUID | None = None
    input_mapping: dict[str, str] = Field(default_factory=dict)
    output_mapping: dict[str, str] = Field(default_factory=dict)
    retry: RetryConfig | None = None


class OrchestrationEdge(BaseModel):
    from_step: str
    to_step: str
    condition: str | None = None


class OrchestrationPlan(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    description: str
    steps: list[OrchestrationStep]
    edges: list[OrchestrationEdge]
    entry_step: str
    error_strategy: str
    compensating_steps: dict[str, str] | None = None
    timeout: int | None = None
    state: dict[str, Any] = Field(default_factory=dict)


class OrchestrationEvent(BaseModel):
    event_type: str
    timestamp: datetime
    step_slug: str | None = None
    workflow_id: UUID | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OrchestrationRun(BaseModel):
    id: UUID
    plan_id: UUID
    org_id: UUID
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    current_step: str | None = None
    completed_steps: list[str] = Field(default_factory=list)
    failed_steps: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class OrchestrationStatus(BaseModel):
    run_id: UUID
    status: str
    progress: str
    current_step: str | None = None
    elapsed_seconds: float


class WorkflowResult(BaseModel):
    run_id: UUID
    workflow_id: UUID
    status: str
    output: dict[str, Any]
    duration_seconds: float
    error: str | None = None


# ---------------------------------------------------------------------------
# Layer 3 — Agent Loops
# ---------------------------------------------------------------------------


class GoalEvaluator(BaseModel):
    evaluator_type: str
    config: dict[str, Any]


class ExitCondition(BaseModel):
    condition_type: str
    config: dict[str, Any]


class AgentLoopDefinition(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    description: str
    agent_id: UUID
    goal: str
    goal_evaluator: GoalEvaluator
    max_iterations: int
    iteration_timeout: int | None = None
    cooldown: int = 0
    reflect_prompt: str | None = None
    reflection_strategy: str = "self_critique"
    accumulate_state: bool = True
    state_schema: dict[str, Any] = Field(default_factory=dict)
    exit_conditions: list[ExitCondition] = Field(default_factory=list)


class LoopEvent(BaseModel):
    event_type: str
    timestamp: datetime
    iteration_num: int
    output: dict[str, Any] | None = None
    reflection: str | None = None
    goal_score: float | None = None
    goal_met: bool | None = None
    final_state: dict[str, Any] | None = None
    reason: str | None = None


class LoopIteration(BaseModel):
    iteration_num: int
    started_at: datetime
    completed_at: datetime
    input_context: dict[str, Any]
    output: dict[str, Any]
    reflection: str | None = None
    goal_score: float | None = None
    goal_met: bool = False
    tokens_used: int | None = None


# ---------------------------------------------------------------------------
# Engagement — output of the Learning Actions system
# ---------------------------------------------------------------------------


class Engagement(BaseModel):
    """A discrete learning experience — the output of the Learning Actions system."""

    id: UUID
    name: str
    description: str
    engagement_type: str  # 'tutoring', 'exercise', 'assessment', 'review', 'reflection'
    source: str  # 'generated' or 'curated'
    knowledge_graph_refs: list[str] = Field(default_factory=list)  # KG concept IDs this targets
    # relevant student dimensions
    student_model_context: dict[str, Any] = Field(default_factory=dict)
    # WDF YAML as dict, if this engagement is a workflow
    workflow_definition: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)
