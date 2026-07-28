"""Shared test doubles for the domain-pack tests (KG-W5 / RAG-1847)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from capillary_actions_sdk.events import AGUIEvent
from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)

from primer_core.skills import SkillRegistry


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
