from __future__ import annotations

import pytest

from capillary_actions_sdk.models.knowledge import RetrievedChunk
from capillary_actions_sdk.ports import KnowledgeBasePort as KnowledgeBasePortFromInit
from capillary_actions_sdk.ports.knowledge import KnowledgeBasePort

# ---------------------------------------------------------------------------
# ABC instantiation — cannot be created directly
# ---------------------------------------------------------------------------


class TestKnowledgeBasePortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            KnowledgeBasePort()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Concrete implementation — subclass that implements retrieve() is allowed
# ---------------------------------------------------------------------------


class ConcreteKnowledgeBasePort(KnowledgeBasePort):
    async def retrieve(
        self, query: str, kb_names: list[str], top_k: int = 5
    ) -> list[RetrievedChunk]:
        return [RetrievedChunk(text=f"chunk for {query}", score=1.0)]


class TestConcreteKnowledgeBasePort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteKnowledgeBasePort()
        assert isinstance(port, KnowledgeBasePort)

    async def test_retrieve_returns_list_of_retrieved_chunks(self):
        port = ConcreteKnowledgeBasePort()
        results = await port.retrieve("what is interest?", ["primer-coop-finance-kb"], top_k=3)
        assert isinstance(results, list)
        assert all(isinstance(chunk, RetrievedChunk) for chunk in results)


# ---------------------------------------------------------------------------
# Public export — KnowledgeBasePort must be reachable from capillary_actions_sdk.ports
# ---------------------------------------------------------------------------


class TestKnowledgeBasePortExported:
    def test_exported_from_ports_init(self):
        assert KnowledgeBasePortFromInit is KnowledgeBasePort
