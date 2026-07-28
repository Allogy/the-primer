"""Per-domain construction test (KG-W5 / RAG-1847).

The same engine construction — byte-identical apart from the pack name — must
work for both domains with zero engine edits. All three engine components are
built here: MemoryCore, EngagementOrchestrator, and InteractionAgent (the only
one that retrieves from the knowledge base).
"""

from __future__ import annotations

from typing import NamedTuple
from uuid import uuid4

import pytest
from capillary_actions_sdk.ports.platform import RunWorkflowResponse
from capillary_actions_sdk.reference.in_memory_memory_store import InMemoryMemoryStore
from pydantic_ai.models.test import TestModel

from primer_core.adapters.capillary import PgVectorKnowledgeBase
from primer_core.domains import load_domain_pack
from primer_core.interaction import InteractionAgent
from primer_core.memory.core import MemoryCore
from primer_core.orchestrator import EngagementOrchestrator
from primer_core.testing.fakes import FakeRunWorkflowPort
from tests.domains.fakes import FakeSearchClient

DOMAINS = ("education", "coop-finance")
FIRST_ENGAGEMENT = {
    "education": "tutor-concept",
    "coop-finance": "explain-product",
}
EXPECTED_KB_NAMES = {
    "education": ["primer-education-kb"],
    "coop-finance": ["primer-coop-finance-kb"],
}
ANSWER = "the model reply"


class Engine(NamedTuple):
    """Everything one domain's construction produces."""

    orchestrator: EngagementOrchestrator
    agent: InteractionAgent
    memory: MemoryCore
    runner: FakeRunWorkflowPort
    search: FakeSearchClient


def _build(domain: str) -> Engine:
    """Construct the whole engine for a domain — identical code for every pack."""
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

    search = FakeSearchClient([{"chunk": f"a {domain} fact", "distance": 0.1}])
    agent = InteractionAgent(
        schema=pack.schema,
        kb=PgVectorKnowledgeBase(search),
        memory=memory,
        model=TestModel(custom_output_text=ANSWER),
    )

    return Engine(orchestrator, agent, memory, runner, search)


@pytest.mark.parametrize("domain", DOMAINS)
def test_engine_constructs_from_the_pack(domain: str) -> None:
    engine = _build(domain)

    assert engine.orchestrator.schema.domain == domain
    assert engine.memory.schema.domain == domain
    assert engine.agent.schema.domain == domain
    assert engine.orchestrator.runner is engine.runner
    assert engine.orchestrator.memory is engine.memory
    assert engine.agent.memory is engine.memory
    assert engine.orchestrator.skills.get(FIRST_ENGAGEMENT[domain]).is_file()


@pytest.mark.parametrize("domain", DOMAINS)
async def test_one_engagement_per_domain_runs_to_completion(domain: str) -> None:
    pack = load_domain_pack(domain)
    engine = _build(domain)
    engagement = FIRST_ENGAGEMENT[domain]
    subject_id = uuid4()

    response = await engine.orchestrator.run_engagement(
        engagement,
        subject_id,
        "thread-1",
        input_data={"topic": "demo"},
    )

    assert response.status == "completed"
    assert response.output == {"answer": "ok"}
    assert response.run_id == f"run-{domain}"

    assert len(engine.runner.requests) == 1
    request = engine.runner.requests[0]
    assert request.workflow_id == pack.skills.workflow_id(engagement)
    assert request.thread_id == "thread-1"
    assert request.input_data == {"topic": "demo"}


@pytest.mark.parametrize("domain", DOMAINS)
async def test_interaction_agent_retrieves_from_the_pack_knowledge_base(domain: str) -> None:
    """The agent must query the domain's own KB — InteractionAgent reads it off the schema."""
    engine = _build(domain)

    reply = await engine.agent.turn(uuid4(), "explain this to me")

    assert reply == ANSWER
    assert engine.search.kb_names_received == [EXPECTED_KB_NAMES[domain]]
    assert engine.search.calls[0][0] == "explain this to me"


async def test_the_two_domains_retrieve_from_different_knowledge_bases() -> None:
    """Guards against a pack leaking another domain's KB wiring into the agent."""
    education = _build("education")
    finance = _build("coop-finance")

    await education.agent.turn(uuid4(), "q")
    await finance.agent.turn(uuid4(), "q")

    assert education.search.kb_names_received == [["primer-education-kb"]]
    assert finance.search.kb_names_received == [["primer-coop-finance-kb"]]
