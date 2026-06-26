"""Knowledge base models — typed return contracts for KnowledgeBasePort."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """A single chunk returned by a knowledge base retrieval query."""

    text: str = Field(..., description="Chunk text content.")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score in [0, 1].")
