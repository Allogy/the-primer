"""Tests for the in-memory engine-port fakes in primer_core.testing.

Covers FakeKnowledgeBase retrieval behavior and FakeRunWorkflowPort
synchronous and streaming workflow behavior.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from capillary_actions_sdk.events import (
    AGUIEventType,
    RunFinishedEvent,
    RunStartedEvent,
)
from capillary_actions_sdk.models.knowledge import RetrievedChunk
from capillary_actions_sdk.ports.knowledge import KnowledgeBasePort
from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)

from primer_core.testing.fakes import FakeKnowledgeBase, FakeRunWorkflowPort


def _chunk(text: str, score: float = 0.9) -> RetrievedChunk:
    return RetrievedChunk(text=text, score=score)


def _workflow_request() -> RunWorkflowRequest:
    return RunWorkflowRequest(
        workflow_id=uuid4(),
        thread_id="thread-123",
        input_data={"concept": "limits"},
        org_id=None,
    )


def _workflow_response() -> RunWorkflowResponse:
    return RunWorkflowResponse(
        run_id="run-123",
        output={"result": "success"},
        status="completed",
    )


class TestFakeKnowledgeBase:
    # ------------------------------------------------------------------
    # Scenario 1: FakeKnowledgeBase is a real KnowledgeBasePort
    # ------------------------------------------------------------------

    def test_is_knowledge_base_port(self) -> None:
        kb = FakeKnowledgeBase()
        assert isinstance(kb, KnowledgeBasePort)

    # ------------------------------------------------------------------
    # Scenario 2: retrieve returns canned RetrievedChunk objects
    # ------------------------------------------------------------------

    async def test_retrieve_returns_seeded_chunks(self) -> None:
        chunk = _chunk("A limit describes the value a function approaches.")
        kb = FakeKnowledgeBase([chunk])

        results = await kb.retrieve("what is a limit", ["primer-education-kb"], top_k=3)

        assert results == [chunk]
        assert all(isinstance(r, RetrievedChunk) for r in results)
        assert results[0].text == "A limit describes the value a function approaches."
        assert results[0].score == pytest.approx(0.9)

    async def test_retrieve_returns_empty_when_no_chunks_seeded(self) -> None:
        kb = FakeKnowledgeBase()
        results = await kb.retrieve("anything", ["kb"], top_k=5)
        assert results == []

    # ------------------------------------------------------------------
    # Scenario 3: retrieve records its calls for assertion
    # ------------------------------------------------------------------

    async def test_retrieve_records_call(self) -> None:
        kb = FakeKnowledgeBase([_chunk("some text")])

        await kb.retrieve("what is a limit", ["primer-education-kb"], 3)

        assert kb.calls == [("what is a limit", ["primer-education-kb"], 3)]

    async def test_retrieve_records_multiple_calls(self) -> None:
        kb = FakeKnowledgeBase([_chunk("text")])

        await kb.retrieve("q1", ["kb-a"], 2)
        await kb.retrieve("q2", ["kb-b", "kb-c"], 5)

        assert kb.calls == [
            ("q1", ["kb-a"], 2),
            ("q2", ["kb-b", "kb-c"], 5),
        ]

    async def test_calls_empty_before_any_retrieve(self) -> None:
        kb = FakeKnowledgeBase([_chunk("text")])
        assert kb.calls == []

    # ------------------------------------------------------------------
    # Scenario 4: retrieve honors top_k
    # ------------------------------------------------------------------

    async def test_retrieve_honors_top_k(self) -> None:
        chunks = [_chunk(f"chunk {i}", score=round(1.0 - i * 0.1, 1)) for i in range(5)]
        kb = FakeKnowledgeBase(chunks)

        results = await kb.retrieve("query", ["kb"], top_k=2)

        assert len(results) == 2
        assert results == chunks[:2]

    async def test_retrieve_top_k_larger_than_available_returns_all(self) -> None:
        chunks = [_chunk("only one")]
        kb = FakeKnowledgeBase(chunks)

        results = await kb.retrieve("query", ["kb"], top_k=10)

        assert len(results) == 1

    async def test_retrieve_top_k_zero_returns_empty(self) -> None:
        kb = FakeKnowledgeBase([_chunk("text")])
        results = await kb.retrieve("query", ["kb"], top_k=0)
        assert results == []

    async def test_retrieve_top_k_negative_returns_empty(self) -> None:
        kb = FakeKnowledgeBase([_chunk("text")])
        results = await kb.retrieve("query", ["kb"], top_k=-1)
        assert results == []

    # ------------------------------------------------------------------
    # Ordering and isolation
    # ------------------------------------------------------------------

    async def test_retrieve_orders_by_descending_score_regardless_of_seed_order(
        self,
    ) -> None:
        low = _chunk("low", score=0.1)
        high = _chunk("high", score=0.9)
        mid = _chunk("mid", score=0.5)
        kb = FakeKnowledgeBase([low, high, mid])

        results = await kb.retrieve("query", ["kb"], top_k=3)

        assert results == [high, mid, low]

    def test_seed_list_mutation_after_construction_does_not_affect_kb(self) -> None:
        chunks = [_chunk("original")]
        kb = FakeKnowledgeBase(chunks)

        chunks.append(_chunk("appended"))

        assert kb._chunks == [_chunk("original")]

    async def test_kb_names_mutation_after_call_does_not_affect_recorded_call(
        self,
    ) -> None:
        kb = FakeKnowledgeBase([_chunk("text")])
        kb_names = ["kb-a"]

        await kb.retrieve("query", kb_names, top_k=1)
        kb_names.append("kb-b")

        assert kb.calls == [("query", ["kb-a"], 1)]


class TestFakeRunWorkflowPort:
    def test_is_run_workflow_port(self) -> None:
        runner = FakeRunWorkflowPort(_workflow_response())

        assert isinstance(runner, RunWorkflowPort)

    def test_requests_empty_before_running(self) -> None:
        runner = FakeRunWorkflowPort(_workflow_response())

        assert runner.requests == []

    async def test_run_sync_records_request_and_returns_response(self) -> None:
        request = _workflow_request()
        response = _workflow_response()
        runner = FakeRunWorkflowPort(response)

        result = await runner.run_sync(request)

        assert result is response
        assert runner.requests == [request]

    async def test_run_yields_started_then_finished(self) -> None:
        request = _workflow_request()
        response = _workflow_response()
        runner = FakeRunWorkflowPort(response)

        events = [event async for event in runner.run(request)]

        assert len(events) == 2

        assert isinstance(events[0], RunStartedEvent)
        assert events[0].event_type == AGUIEventType.RUN_STARTED

        assert isinstance(events[1], RunFinishedEvent)
        assert events[1].event_type == AGUIEventType.RUN_FINISHED

        assert events[0].thread_id == request.thread_id
        assert events[1].thread_id == request.thread_id

        assert events[0].run_id == response.run_id
        assert events[1].run_id == response.run_id

        assert runner.requests == [request]
