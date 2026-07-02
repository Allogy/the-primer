"""In-memory test doubles for primer_core engine ports.

Both fakes live here so the eval harness and demos can import from a single
importable module (G5 — fakes are engine code, not test-only).

Owners:
  FakeKnowledgeBase   — KG-W2 (Rianna)
  FakeRunWorkflowPort — DS-W2 (Joseph)  ← placeholder below, Joseph adds this
"""

from __future__ import annotations

from capillary_actions_sdk.models.knowledge import RetrievedChunk
from capillary_actions_sdk.ports.knowledge import KnowledgeBasePort


class FakeKnowledgeBase(KnowledgeBasePort):
    """Deterministic, in-memory KnowledgeBasePort for tests and offline demos.

    Seed it with canned chunks; every retrieve() call returns them (truncated
    to top_k) and records the call for later assertion.

    Usage::

        kb = FakeKnowledgeBase([RetrievedChunk(text='A limit describes...', score=0.9)])
        chunks = await kb.retrieve('what is a limit', ['primer-education-kb'], top_k=3)
        assert kb.calls == [('what is a limit', ['primer-education-kb'], 3)]
    """

    def __init__(self, chunks: list[RetrievedChunk] | None = None) -> None:
        self._chunks: list[RetrievedChunk] = sorted(
            chunks or [], key=lambda c: c.score, reverse=True
        )
        self.calls: list[tuple[str, list[str], int]] = []

    async def retrieve(
        self, query: str, kb_names: list[str], top_k: int = 5
    ) -> list[RetrievedChunk]:
        self.calls.append((query, list(kb_names), top_k))
        if top_k <= 0:
            return []
        return self._chunks[:top_k]


# ---------------------------------------------------------------------------
# FakeRunWorkflowPort — DS-W2 (Joseph)
# Add FakeRunWorkflowPort here. It must implement RunWorkflowPort from
# capillary_actions_sdk.ports.platform and expose a .requests attribute for
# assertion. See DS-W2 acceptance criteria.
# ---------------------------------------------------------------------------
