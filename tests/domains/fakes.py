"""Shared test doubles for the domain-pack tests (KG-W5 / RAG-1847, KG-W4/KG-W6)."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

from capillary_actions_sdk.events import AGUIEvent
from capillary_actions_sdk.models.knowledge import RetrievedChunk
from capillary_actions_sdk.ports.knowledge import KnowledgeBasePort
from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)

from primer_core.skills import SkillRegistry

MIN_RANKING_TOKEN_LENGTH = 4


def ranking_tokens(text: str) -> set[str]:
    """Significant lowercase tokens of *text* — short stopwords drop out."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= MIN_RANKING_TOKEN_LENGTH
    }


class CorpusKnowledgeBase(KnowledgeBasePort):
    """Deterministic corrective-retriever stand-in with a per-KB corpus.

    Chunks are seeded under knowledge base names. ``retrieve`` searches only the
    requested ``kb_names`` and ranks candidates by how many significant query
    tokens their text shares (score breaks ties), so what comes back depends on
    the query and the KB routing — not on seed order. Every call and its result
    are recorded for assertion.
    """

    def __init__(self, corpus: dict[str, list[RetrievedChunk]]) -> None:
        self._corpus = {kb_name: list(chunks) for kb_name, chunks in corpus.items()}
        self.calls: list[tuple[str, list[str], int]] = []
        self.results: list[list[RetrievedChunk]] = []

    async def retrieve(
        self, query: str, kb_names: list[str], top_k: int = 5
    ) -> list[RetrievedChunk]:
        self.calls.append((query, list(kb_names), top_k))
        query_tokens = ranking_tokens(query)

        candidates = [chunk for kb_name in kb_names for chunk in self._corpus.get(kb_name, [])]
        ranked = sorted(
            (chunk for chunk in candidates if query_tokens & ranking_tokens(chunk.text)),
            key=lambda chunk: (len(query_tokens & ranking_tokens(chunk.text)), chunk.score),
            reverse=True,
        )

        result = ranked[:top_k] if top_k > 0 else []
        self.results.append(result)
        return result


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


class WritebackRunner(RunWorkflowPort):
    """Return an engagement outcome containing schema-aligned write-back data."""

    def __init__(self) -> None:
        self.requests: list[RunWorkflowRequest] = []

    async def run_sync(
        self,
        request: RunWorkflowRequest,
    ) -> RunWorkflowResponse:
        self.requests.append(request)

        return RunWorkflowResponse(
            run_id="run-123",
            status="completed",
            output={
                "answer": "Gravity is 9.8 m/s/s.",
                "writeback": {
                    "dimension": "history",
                    "content": {
                        "courses": ["physics-1"],
                    },
                },
            },
        )

    async def run(
        self,
        request: RunWorkflowRequest,
    ) -> AsyncIterator[AGUIEvent]:
        raise AssertionError("This integration test should use run_engagement, not streaming")
        yield  # pragma: no cover


def _skills() -> SkillRegistry:
    skills = SkillRegistry()
    skills.register(
        "tutor-concept",
        "src/primer_core/wdfs/tutor-concept.yaml",
    )
    skills.register(
        "foundational",
        "src/primer_core/wdfs/tutor-concept.yaml",
    )
    return skills
