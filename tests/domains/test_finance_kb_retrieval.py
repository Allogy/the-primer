"""Finance KB retrieval over the W3 pgvector adapter (KG-W5 / RAG-1847).

The pack supplies the kb_names; PgVectorKnowledgeBase is exercised against a
fake search client so the test stays offline and deterministic.
"""

from __future__ import annotations

import pytest
from capillary_actions_sdk.models.knowledge import RetrievedChunk

from primer_core.adapters.capillary import PgVectorKnowledgeBase
from primer_core.domains import load_domain_pack
from tests.domains.fakes import FakeSearchClient

FINANCE_ROWS = [
    {
        "chunk": (
            "A credit union share account is a member's ownership stake in the "
            "cooperative; the balance both funds member lending and pays dividends."
        ),
        "distance": 0.08,
    },
    {
        "chunk": (
            "Share certificates lock funds for a fixed term at a higher dividend "
            "rate than a regular share account."
        ),
        "distance": 0.31,
    },
]


def test_retrieved_chunks_carry_text_and_score_only() -> None:
    """Freezes the contract point: chunks have no provenance field yet.

    If the SDK ever adds one (source doc, kb name, offsets), this test fails and
    the finance packs get to decide what to surface rather than inheriting it.
    """
    assert set(RetrievedChunk.model_fields) == {"text", "score"}


async def test_retrieves_finance_chunks_for_the_pack_kb() -> None:
    pack = load_domain_pack("coop-finance")
    client = FakeSearchClient(FINANCE_ROWS)
    kb = PgVectorKnowledgeBase(client)

    chunks = await kb.retrieve("what is a credit union share account?", pack.kb_names)

    assert len(chunks) == 2
    assert all(isinstance(chunk, RetrievedChunk) for chunk in chunks)

    # Rows map to chunks positionally, so ranking survives the adapter.
    assert [chunk.text for chunk in chunks] == [row["chunk"] for row in FINANCE_ROWS]
    assert chunks[0].score == pytest.approx(0.92)
    assert chunks[1].score == pytest.approx(0.69)


async def test_retrieval_is_wired_to_the_finance_knowledge_base() -> None:
    pack = load_domain_pack("coop-finance")
    client = FakeSearchClient(FINANCE_ROWS)
    kb = PgVectorKnowledgeBase(client)

    await kb.retrieve("share certificate terms", pack.kb_names, top_k=3)

    assert client.calls == [("share certificate terms", ["primer-coop-finance-kb"], 3)]


async def test_education_and_finance_packs_target_different_knowledge_bases() -> None:
    education = load_domain_pack("education")
    finance = load_domain_pack("coop-finance")

    assert education.kb_names != finance.kb_names
