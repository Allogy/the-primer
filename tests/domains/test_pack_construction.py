"""Per-domain construction test (KG-W5 / RAG-1847).

The same engine construction — byte-identical apart from the pack name — must
work for both domains with zero engine edits.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from capillary_actions_sdk.ports.platform import RunWorkflowResponse
from capillary_actions_sdk.reference.in_memory_memory_store import InMemoryMemoryStore

from primer_core.domains import load_domain_pack
from primer_core.memory.core import MemoryCore
from primer_core.orchestrator import EngagementOrchestrator
from primer_core.testing.fakes import FakeRunWorkflowPort

DOMAINS = ("education", "coop-finance")
FIRST_ENGAGEMENT = {
    "education": "tutor-concept",
    "coop-finance": "explain-product",
}


def _build(domain: str) -> tuple[EngagementOrchestrator, FakeRunWorkflowPort, MemoryCore]:
    """Construct the engine for a domain — identical code for every pack."""
    pack = load_domain_pack(domain)
    store = InMemoryMemoryStore()
    memory = MemoryCore(schema=pack.schema, store=store)
    runner = FakeRunWorkflowPort(
        RunWorkflowResponse(
            run_id=f"run-{domain}",
            output={"answer": "ok"},
            status="completed",
        )
    )
    orchestrator = EngagementOrchestrator(
        schema=pack.schema,
        runner=runner,
        memory=memory,
        skills=pack.skills,
    )
    return orchestrator, runner, memory


@pytest.mark.parametrize("domain", DOMAINS)
def test_engine_constructs_from_the_pack(domain: str) -> None:
    orchestrator, runner, memory = _build(domain)

    assert orchestrator.schema.domain == domain
    assert memory.schema.domain == domain
    assert orchestrator.runner is runner
    assert orchestrator.memory is memory
    assert orchestrator.skills.get(FIRST_ENGAGEMENT[domain]).is_file()


@pytest.mark.parametrize("domain", DOMAINS)
async def test_one_engagement_per_domain_runs_to_completion(domain: str) -> None:
    pack = load_domain_pack(domain)
    orchestrator, runner, _ = _build(domain)
    engagement = FIRST_ENGAGEMENT[domain]
    subject_id = uuid4()

    response = await orchestrator.run_engagement(
        engagement,
        subject_id,
        "thread-1",
        input_data={"topic": "demo"},
    )

    assert response.status == "completed"
    assert response.output == {"answer": "ok"}
    assert response.run_id == f"run-{domain}"

    assert len(runner.requests) == 1
    request = runner.requests[0]
    assert request.workflow_id == pack.skills.workflow_id(engagement)
    assert request.thread_id == "thread-1"
    assert request.input_data == {"topic": "demo"}
