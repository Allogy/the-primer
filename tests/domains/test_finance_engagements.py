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

# Engagements whose WDF must persist its outcome to member memory.
WRITEBACK_ENGAGEMENTS = (
    "suggest-allocation",
    "assess-readiness",
)

# The node vocabulary the coop-finance WDFs are authored in.
WDF_NODE_TYPES = frozenset({"retrieval", "interaction", "function", "output", "complete"})

GROUNDED_LIQUIDITY_FACT = (
    "Members should preserve sufficient liquid reserves before increasing long-term allocations."
)

LIQUIDITY_RECOMMENDATION = "Preserve a liquid reserve before increasing long-term allocations."

READINESS_NOTES = "The member should clarify the expected time horizon before proceeding."


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
                    "recommendation": LIQUIDITY_RECOMMENDATION,
                    "rationale": GROUNDED_LIQUIDITY_FACT,
                    "confidence": confidence,
                },
                "suggestion_sources": [
                    "finance-kb-allocation-001",
                    "finance-kb-allocation-002",
                    "finance-kb-allocation-003",
                    "finance-kb-allocation-004",
                ],
                # Mirrors the suggest-allocation WDF's declared writeback:
                # dimension `goals`, content keyed by the manifest fields
                # `targets`/`priorities`, sourced from the recommendation and
                # rationale outputs.
                "writeback": {
                    "dimension": "goals",
                    "content": {
                        "targets": LIQUIDITY_RECOMMENDATION,
                        "priorities": GROUNDED_LIQUIDITY_FACT,
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
                "notes": READINESS_NOTES,
                "readiness_sources": ["finance-kb-readiness-001"],
                # Mirrors the assess-readiness WDF's declared writeback:
                # dimension `risk_appetite`, content keyed by the manifest
                # fields `tolerance`/`horizon`, sourced from the readiness and
                # assessment-notes outputs.
                "writeback": {
                    "dimension": "risk_appetite",
                    "content": {
                        "tolerance": "partial",
                        "horizon": READINESS_NOTES,
                    },
                },
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


def _declared_writeback(engagement: str) -> dict:
    """Return the writeback mapping declared by the engagement WDF's output node."""
    pack = load_domain_pack("coop-finance")
    wdf = pack.skills.load_wdf(engagement)

    for node in wdf["nodes"].values():
        if node.get("type") == "output" and "writeback" in node.get("output", {}):
            return node["output"]["writeback"]

    raise AssertionError(f"WDF {engagement!r} declares no writeback")


@pytest.mark.parametrize("engagement", FINANCE_ENGAGEMENTS)
def test_finance_wdfs_are_contract_valid_and_internally_consistent(engagement: str) -> None:
    """The packaged WDFs are internally consistent and manifest-aligned.

    Every node carries a known type, every `next` edge resolves, the graph
    walks entry -> exit visiting each declared node exactly once, and any
    declared writeback targets a manifest dimension with dict content keyed
    only by that dimension's declared fields — the shape write_back_outcome
    and MemoryCore.ingest require.
    """
    pack = load_domain_pack("coop-finance")
    wdf = pack.skills.load_wdf(engagement)

    assert {"name", "entry", "exit", "nodes"} <= wdf.keys()
    assert wdf["name"] == engagement

    nodes = wdf["nodes"]
    assert wdf["entry"] in nodes
    assert wdf["exit"] in nodes

    for node_name, node in nodes.items():
        assert isinstance(node, dict)
        assert node.get("type") in WDF_NODE_TYPES, f"node {node_name!r} has an unknown type"
        if node_name == wdf["exit"]:
            assert node["type"] == "complete"
            assert "next" not in node
        else:
            assert node["type"] != "complete"
            assert node["next"] in nodes

    # Walk entry -> exit: every declared node participates, no cycles.
    visited = [wdf["entry"]]
    while visited[-1] != wdf["exit"]:
        successor = nodes[visited[-1]]["next"]
        assert successor not in visited
        visited.append(successor)
    assert set(visited) == set(nodes)

    writebacks = [
        node["output"]["writeback"]
        for node in nodes.values()
        if node.get("type") == "output" and "writeback" in node.get("output", {})
    ]
    if engagement in WRITEBACK_ENGAGEMENTS:
        assert writebacks, f"WDF {engagement!r} must persist its outcome via a writeback"
    for writeback in writebacks:
        dimension = pack.schema.dimension(writeback["dimension"])
        assert dimension is not None, (
            f"writeback dimension {writeback['dimension']!r} is not declared in the manifest"
        )
        assert isinstance(writeback["content"], dict), "writeback content must be a mapping"
        assert set(writeback["content"]) <= set(dimension.fields)


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

    assert suggestion.recommendation == LIQUIDITY_RECOMMENDATION
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


@pytest.mark.parametrize("engagement", WRITEBACK_ENGAGEMENTS)
async def test_finance_writeback_uses_existing_after_engagement_hook(
    engagement: str,
) -> None:
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
        skill_name=engagement,
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
    declared = _declared_writeback(engagement)
    expected = _finance_responses()[pack.skills.workflow_id(engagement)].output["writeback"]

    # The entry lands under the dimension the WDF itself declares, with the
    # content fields the WDF maps, populated as the fixture emitted them.
    assert entry.dimension == declared["dimension"]
    assert set(entry.content) == set(declared["content"])
    assert entry.content == expected["content"]
    assert entry.metadata["source"] == "primer_core.orchestrator"
