from __future__ import annotations

import pytest
from capillary_actions_sdk.ports.knowledge import KnowledgeBasePort

from primer_core.adapters.capillary import PgVectorKnowledgeBase


class FakeSearchClient:
    """Records calls and returns a canned response, standing in for the real pgvector client."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.calls: list[tuple[str, list[str], int]] = []

    async def search(self, query: str, kb_names: list[str], top_k: int) -> list[dict]:
        self.calls.append((query, list(kb_names), top_k))
        return self._rows


async def test_is_a_real_knowledge_base_port():
    kb = PgVectorKnowledgeBase(FakeSearchClient([]))
    assert isinstance(kb, KnowledgeBasePort)


async def test_retrieve_maps_chunk_and_distance_to_text_and_score():
    client = FakeSearchClient(
        [{"chunk": "A derivative measures rate of change.", "distance": 0.12}]
    )
    kb = PgVectorKnowledgeBase(client)

    chunks = await kb.retrieve("what is a derivative?", ["primer-education-kb"], top_k=2)

    assert len(chunks) == 1
    assert chunks[0].text == "A derivative measures rate of change."
    assert chunks[0].score == pytest.approx(0.88)


async def test_retrieve_passes_pre_scored_row_through_unchanged():
    client = FakeSearchClient([{"text": "pre-scored", "score": 0.9}])
    kb = PgVectorKnowledgeBase(client)

    chunks = await kb.retrieve("q", ["primer-education-kb"])

    assert chunks[0].text == "pre-scored"
    assert chunks[0].score == pytest.approx(0.9)


async def test_score_is_clamped_into_unit_interval():
    client = FakeSearchClient([{"chunk": "far", "distance": 1.7}])
    kb = PgVectorKnowledgeBase(client)

    chunks = await kb.retrieve("q", ["primer-education-kb"])

    assert chunks[0].score == 0.0


async def test_retrieve_forwards_query_kb_names_and_top_k():
    client = FakeSearchClient([])
    kb = PgVectorKnowledgeBase(client)

    await kb.retrieve("q", ["primer-education-kb", "extra-kb"], top_k=7)

    assert client.calls == [("q", ["primer-education-kb", "extra-kb"], 7)]


async def test_top_k_defaults_to_five():
    client = FakeSearchClient([])
    kb = PgVectorKnowledgeBase(client)

    await kb.retrieve("q", ["primer-education-kb"])

    assert client.calls[0][2] == 5


async def test_empty_client_response_returns_empty_list():
    client = FakeSearchClient([])
    kb = PgVectorKnowledgeBase(client)

    chunks = await kb.retrieve("q", ["primer-education-kb"])

    assert chunks == []
