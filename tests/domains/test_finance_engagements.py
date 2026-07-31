from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from capillary_actions_sdk.events import AGUIEvent
from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)
from capillary_actions_sdk.reference.in_memory_memory_store import (
    InMemoryMemoryStore,
)
from pydantic import ValidationError

from primer_core.domains import load_domain_pack
from primer_core.domains.coop_finance.models import (
    AllocationSuggestion,
    derive_confidence,
    profile_completeness,
)
from primer_core.memory.core import MemoryCore
from primer_core.orchestrator import (
    EngagementOrchestrator,
    HookEvent,
    HookRegistry,
    write_back_outcome,
)


def test_allocation_suggestion_accepts_valid_payload() -> None:
    suggestion = AllocationSuggestion(
        recommendation="Maintain sufficient liquid reserves before allocating more.",
        rationale=(
            "Retrieved cooperative-finance guidance prioritizes liquidity "
            "before increasing longer-term allocations."
        ),
        confidence=0.7,
    )

    assert suggestion.recommendation == (
        "Maintain sufficient liquid reserves before allocating more."
    )
    assert suggestion.confidence == 0.7


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_allocation_suggestion_rejects_invalid_confidence(
    confidence: float,
) -> None:
    with pytest.raises(ValidationError):
        AllocationSuggestion(
            recommendation="Example recommendation",
            rationale="Example rationale",
            confidence=confidence,
        )


@pytest.mark.parametrize("field", ["recommendation", "rationale"])
def test_allocation_suggestion_rejects_blank_text(field: str) -> None:
    payload = {
        "recommendation": "Example recommendation",
        "rationale": "Example rationale",
        "confidence": 0.5,
    }
    payload[field] = "   "

    with pytest.raises(ValidationError):
        AllocationSuggestion.model_validate(payload)


def test_allocation_suggestion_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AllocationSuggestion(
            recommendation="Example recommendation",
            rationale="Example rationale",
            confidence=0.5,
            unsupported_field="unexpected",
        )


def test_allocation_suggestion_from_outcome_output() -> None:
    output = {
        "suggestion": {
            "recommendation": "Preserve liquidity.",
            "rationale": "The retrieved guidance emphasizes liquid reserves.",
            "confidence": 0.55,
        },
        "suggestion_sources": ["finance-kb-001"],
    }

    suggestion = AllocationSuggestion.from_outcome_output(output)

    assert suggestion.recommendation == "Preserve liquidity."
    assert suggestion.confidence == 0.55


def test_allocation_suggestion_requires_suggestion_key() -> None:
    with pytest.raises(ValueError, match="suggestion"):
        AllocationSuggestion.from_outcome_output({})


def test_allocation_suggestion_requires_mapping_payload() -> None:
    with pytest.raises(ValueError, match="must be a mapping"):
        AllocationSuggestion.from_outcome_output({"suggestion": "not-a-mapping"})


def test_derive_confidence_is_deterministic() -> None:
    first = derive_confidence(
        retrieved_passage_count=3,
        profile_completeness=0.5,
    )
    second = derive_confidence(
        retrieved_passage_count=3,
        profile_completeness=0.5,
    )

    assert first == second


def test_derive_confidence_saturates_after_four_passages() -> None:
    saturated = derive_confidence(
        retrieved_passage_count=4,
        profile_completeness=0.5,
    )
    additional_evidence = derive_confidence(
        retrieved_passage_count=20,
        profile_completeness=0.5,
    )

    assert saturated == additional_evidence


@pytest.mark.parametrize(
    ("passage_count", "completeness"),
    [
        (-1, 0.5),
        (1, -0.01),
        (1, 1.01),
    ],
)
def test_derive_confidence_rejects_invalid_inputs(
    passage_count: int,
    completeness: float,
) -> None:
    with pytest.raises(ValueError):
        derive_confidence(
            retrieved_passage_count=passage_count,
            profile_completeness=completeness,
        )


def test_profile_completeness_counts_expected_dimensions() -> None:
    completeness = profile_completeness(
        populated_dimensions=["goal", "liquidity", "unrelated"],
        expected_dimensions=["goal", "liquidity", "time_horizon", "risk"],
    )

    assert completeness == 0.5


def test_profile_completeness_returns_zero_without_expectations() -> None:
    assert profile_completeness(["goal"], []) == 0.0


FINANCE_ENGAGEMENTS = (
    "explain-product",
    "suggest-allocation",
    "assess-readiness",
)

GROUNDED_LIQUIDITY_FACT = (
    "Members should preserve sufficient liquid reserves before increasing long-term allocations."
)


class FinanceEngagementRunner(RunWorkflowPort):
    """Return deterministic outcomes for the three finance engagements."""

    def __init__(
        self,
        responses: dict[UUID, RunWorkflowResponse],
    ) -> None:
        self._responses = responses
        self.requests: list[RunWorkflowRequest] = []

    async def run_sync(
        self,
        request: RunWorkflowRequest,
    ) -> RunWorkflowResponse:
        self.requests.append(request)

        try:
            return self._responses[request.workflow_id]
        except KeyError as exc:
            raise AssertionError(f"unexpected workflow id: {request.workflow_id}") from exc

    async def run(
        self,
        request: RunWorkflowRequest,
    ) -> AsyncIterator[AGUIEvent]:
        raise AssertionError("Finance engagement tests must use the non-streaming path")
        yield  # pragma: no cover


def _finance_responses() -> dict[UUID, RunWorkflowResponse]:
    pack = load_domain_pack("coop-finance")

    confidence = derive_confidence(
        retrieved_passage_count=4,
        profile_completeness=0.75,
    )

    return {
        pack.skills.workflow_id("explain-product"): RunWorkflowResponse(
            run_id="run-explain-product",
            status="completed",
            output={
                "explanation": (
                    "This product should be evaluated against the member's "
                    "goals, obligations, and available liquidity."
                ),
                "explanation_sources": ["finance-kb-product-001"],
            },
        ),
        pack.skills.workflow_id("suggest-allocation"): RunWorkflowResponse(
            run_id="run-suggest-allocation",
            status="completed",
            output={
                "suggestion": {
                    "recommendation": (
                        "Preserve a liquid reserve before increasing long-term allocations."
                    ),
                    "rationale": GROUNDED_LIQUIDITY_FACT,
                    "confidence": confidence,
                },
                "suggestion_sources": [
                    "finance-kb-allocation-001",
                    "finance-kb-allocation-002",
                    "finance-kb-allocation-003",
                    "finance-kb-allocation-004",
                ],
                "writeback": {
                    "dimension": "goals",
                    "content": {
                        "priorities": ["preserve_liquidity"],
                    },
                },
            },
        ),
        pack.skills.workflow_id("assess-readiness"): RunWorkflowResponse(
            run_id="run-assess-readiness",
            status="completed",
            output={
                "readiness": "partial",
                "unmet_criteria": ["time_horizon"],
                "notes": ("The member should clarify the expected time horizon before proceeding."),
                "readiness_sources": ["finance-kb-readiness-001"],
            },
        ),
    }


def _build_finance_orchestrator(
    *,
    hooks: HookRegistry | None = None,
    memory: MemoryCore | None = None,
) -> tuple[
    EngagementOrchestrator,
    FinanceEngagementRunner,
    MemoryCore,
]:
    pack = load_domain_pack("coop-finance")

    runner = FinanceEngagementRunner(_finance_responses())
    finance_memory = memory or MemoryCore(
        schema=pack.schema,
        store=InMemoryMemoryStore(),
    )

    orchestrator = EngagementOrchestrator(
        schema=pack.schema,
        runner=runner,
        memory=finance_memory,
        skills=pack.skills,
        hooks=hooks,
    )

    return orchestrator, runner, finance_memory


@pytest.mark.parametrize("engagement", FINANCE_ENGAGEMENTS)
async def test_finance_engagement_runs_on_existing_orchestrator(
    engagement: str,
) -> None:
    pack = load_domain_pack("coop-finance")
    orchestrator, runner, _ = _build_finance_orchestrator()
    subject_id = uuid4()

    response = await orchestrator.run_engagement(
        skill_name=engagement,
        subject_id=subject_id,
        thread_id=f"thread-{engagement}",
        input_data={
            "member_profile": {
                "goals": "build long-term savings",
                "risk_appetite": "moderate",
            },
        },
    )

    assert response.status == "completed"
    assert response.output
    assert response.run_id == f"run-{engagement}"

    assert len(runner.requests) == 1
    request = runner.requests[0]

    assert request.workflow_id == pack.skills.workflow_id(engagement)
    assert request.thread_id == f"thread-{engagement}"


async def test_suggest_allocation_returns_structured_suggestion() -> None:
    orchestrator, runner, _ = _build_finance_orchestrator()

    response = await orchestrator.run_engagement(
        skill_name="suggest-allocation",
        subject_id=uuid4(),
        thread_id="thread-suggestion",
        input_data={
            "member_profile": {
                "financial_history": "stable",
                "risk_appetite": "moderate",
                "goals": "long-term savings",
            },
        },
    )

    suggestion = AllocationSuggestion.from_outcome_output(response.output)

    assert suggestion.recommendation == (
        "Preserve a liquid reserve before increasing long-term allocations."
    )
    assert suggestion.rationale == GROUNDED_LIQUIDITY_FACT
    assert suggestion.confidence == derive_confidence(
        retrieved_passage_count=4,
        profile_completeness=0.75,
    )

    assert response.output["suggestion_sources"] == [
        "finance-kb-allocation-001",
        "finance-kb-allocation-002",
        "finance-kb-allocation-003",
        "finance-kb-allocation-004",
    ]

    assert len(runner.requests) == 1


async def test_finance_writeback_uses_existing_after_engagement_hook() -> None:
    pack = load_domain_pack("coop-finance")
    memory = MemoryCore(
        schema=pack.schema,
        store=InMemoryMemoryStore(),
    )

    hooks = HookRegistry()
    hooks.register(
        HookEvent.AFTER_ENGAGEMENT,
        write_back_outcome,
    )

    orchestrator, _, _ = _build_finance_orchestrator(
        hooks=hooks,
        memory=memory,
    )

    subject_id = uuid4()

    await orchestrator.run_engagement(
        skill_name="suggest-allocation",
        subject_id=subject_id,
        thread_id="thread-writeback",
        input_data={
            "member_profile": {
                "goals": "build long-term savings",
            },
        },
    )

    working_memory = await memory.assemble_working_memory(subject_id)

    assert len(working_memory.entries) == 1

    entry = working_memory.entries[0]

    assert entry.dimension == "goals"
    assert entry.content == {
        "priorities": ["preserve_liquidity"],
    }
    assert entry.metadata["source"] == "primer_core.orchestrator"
