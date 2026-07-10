"""PgVectorKnowledgeBase — KnowledgeBasePort adapter over the platform's pgvector KB.

The pgvector search client is injected at construction time; this module has
no httpx/network import on the call path (the real HTTP client is constructed
at the application edge and exercised only in DS-W3's manual live smoke).
"""

from __future__ import annotations

from typing import Protocol

from capillary_actions_sdk.models.knowledge import RetrievedChunk
from capillary_actions_sdk.ports.knowledge import KnowledgeBasePort


class PgVectorSearchClient(Protocol):
    """Injected client that performs the actual pgvector similarity search."""

    async def search(self, query: str, kb_names: list[str], top_k: int) -> list[dict]: ...


def _row_to_chunk(row: dict) -> RetrievedChunk:
    text = row.get("text", row.get("chunk", ""))
    if "score" in row:
        score = row["score"]
    elif "distance" in row:
        score = max(0.0, min(1.0, 1.0 - row["distance"]))
    else:
        score = 0.0
    return RetrievedChunk(text=text, score=score)


class PgVectorKnowledgeBase(KnowledgeBasePort):
    """KnowledgeBasePort backed by the platform's pgvector KB via an injected client."""

    def __init__(self, client: PgVectorSearchClient) -> None:
        self._client = client

    async def retrieve(
        self, query: str, kb_names: list[str], top_k: int = 5
    ) -> list[RetrievedChunk]:
        rows = await self._client.search(query, kb_names, top_k)
        return [_row_to_chunk(row) for row in rows]
