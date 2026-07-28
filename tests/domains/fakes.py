"""Shared test doubles for the domain-pack tests (KG-W5 / RAG-1847)."""

from __future__ import annotations


class FakeSearchClient:
    """Records calls and returns canned rows, standing in for the pgvector client.

    Mirrors the PgVectorSearchClient protocol so PgVectorKnowledgeBase can be
    driven offline while still proving which kb_names reached the search layer.
    """

    def __init__(self, rows: list[dict] | None = None) -> None:
        self._rows = rows or []
        self.calls: list[tuple[str, list[str], int]] = []

    async def search(self, query: str, kb_names: list[str], top_k: int) -> list[dict]:
        self.calls.append((query, list(kb_names), top_k))
        return self._rows

    @property
    def kb_names_received(self) -> list[list[str]]:
        """The kb_names argument of every recorded search call."""
        return [kb_names for _, kb_names, _ in self.calls]
