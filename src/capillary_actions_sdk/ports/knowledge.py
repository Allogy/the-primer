"""KnowledgeBasePort — retrieval abstraction for domain knowledge bases."""

from __future__ import annotations

from abc import ABC, abstractmethod

from capillary_actions_sdk.models.knowledge import RetrievedChunk


class KnowledgeBasePort(ABC):
    """Outbound port for retrieving chunks from a domain knowledge base.

    Distinct from KnowledgeGraphPort (structured concept graphs).
    Adapters implement this to back corrective-RAG and similar retrieval strategies.
    """

    @abstractmethod
    async def retrieve(
        self, query: str, kb_names: list[str], top_k: int = 5
    ) -> list[RetrievedChunk]:
        """Retrieve the top-k chunks relevant to *query* from the named knowledge bases.

        Args:
            query: Free-text retrieval query.
            kb_names: One or more knowledge base identifiers to search.
            top_k: Maximum number of chunks to return.

        Returns:
            List of ``RetrievedChunk`` instances ordered by descending relevance score.
        """
        ...
