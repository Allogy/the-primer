"""Finance KB retrieval over the W3 pgvector adapter (KG-W5 / RAG-1847).

The pack supplies the kb_names; PgVectorKnowledgeBase is exercised against a
fake search client so the test stays offline and deterministic.
"""

from __future__ import annotations

import pytest
from capillary_actions_sdk.models.knowledge import RetrievedChunk

from primer_core.adapters.capillary import PgVectorKnowledgeBase
from primer_core.domains import load_domain_pack

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


class FakeSearchClient:
    """Records calls and returns canned finance rows, standing in for the pgvector client."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, list[str], int]] = []

    async def search(self, query: str, kb_names: list[str], top_k: int) -> list[dict]:
        self.calls.append((query, list(kb_names), top_k))
        return self._rows


async def test_retrieves_on_topic_finance_chunks_for_the_pack_kb() -> None:
    pack = load_domain_pack("coop-finance")
    client = FakeSearchClient(FINANCE_ROWS)
    kb = PgVectorKnowledgeBase(client)

    chunks = await kb.retrieve("what is a credit union share account?", pack.kb_names)

    assert len(chunks) == 2
    assert all(isinstance(chunk, RetrievedChunk) for chunk in chunks)
    assert "share account" in chunks[0].text
    assert all(0.0 <= chunk.score <= 1.0 for chunk in chunks)
    assert chunks[0].score == pytest.approx(0.92)


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
