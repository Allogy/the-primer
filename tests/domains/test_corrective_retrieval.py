"""Corrective retrieval quality on the struggle -> re-teach adaptive path (KG-W4).

KG-W5 proved per-domain KB *wiring*; this story proves the *content* served on
the adaptive path: when a struggling learner is routed to the easier engagement,
retrieval returns on-topic chunks for the same concept at the simpler level, and
the query that reaches the KB is the re-teach one, not the failed one verbatim.

Difficulty is a property of the seeded fixtures and the re-teach query, never of
the engine: chunks carry their level in their own text, and the corrective
retriever stand-in ranks by lexical overlap with the query, so every on-topic
assertion exercises the query and KB routing rather than echoing seed order.

Scenario 1 drives the full loop on the coop-finance pack because the struggle
hook derives the easier engagement from ``schema.engagements`` and coop-finance
is the pack that ships more than one real engagement. The education pack ships a
single real engagement (plus the ``'...'`` placeholder), so its corrective
re-teach re-runs ``tutor-concept`` itself — Scenario 2 covers that pack's KB
routing, per its Gherkin.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from capillary_actions_sdk.models.knowledge import RetrievedChunk
from capillary_actions_sdk.ports.knowledge import KnowledgeBasePort
from capillary_actions_sdk.ports.platform import RunWorkflowResponse
from pydantic_ai.models.test import TestModel

from primer_core.adapters.capillary.file_memory_store import FileMemoryStore
from primer_core.domains import load_domain_pack
from primer_core.interaction import InteractionAgent
from primer_core.memory.core import MemoryCore
from primer_core.orchestrator.engagement import EngagementOrchestrator
from primer_core.orchestrator.hooks import HookContext, HookEvent, HookRegistry
from primer_core.orchestrator.writeback import on_struggle
from primer_core.testing.fakes import FakeRunWorkflowPort

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


# --- Coop-finance fixtures: one concept (share certificates) at two levels ---

ADVANCED_CERTIFICATE_CHUNK = RetrievedChunk(
    text=(
        "Advanced strategy: laddering share certificates across staggered maturities "
        "trades liquidity for extra yield."
    ),
    score=0.9,
)

FOUNDATIONAL_CERTIFICATE_CHUNK = RetrievedChunk(
    text=(
        "Share certificates basics: a share certificate locks savings for a fixed term "
        "and pays a set dividend."
    ),
    score=0.8,
)

UNRELATED_OVERDRAFT_CHUNK = RetrievedChunk(
    text="Overdraft protection transfers funds automatically when checking balances fall short.",
    score=0.7,
)

ORIGINAL_FAILED_QUERY = (
    "what laddering of share certificates across staggered maturities gives the best yield"
)

# --- Education fixtures for the cross-domain-bleed scenario ---

FRACTIONS_FOUNDATIONS_CHUNK = RetrievedChunk(
    text="Fractions basics: a fraction names equal parts of one whole, such as half of a pizza.",
    score=0.85,
)

# Deliberate bait: shares a ranking token ("basics") with the education re-teach
# query and carries the highest score in the corpus, so it WOULD surface if
# retrieval ever searched the finance KB from the education pack.
FINANCE_BAIT_CHUNK = RetrievedChunk(
    text="Dividend basics: a share account pays dividends from the cooperative earnings.",
    score=0.95,
)


def _struggling_runner() -> FakeRunWorkflowPort:
    return FakeRunWorkflowPort(
        RunWorkflowResponse(
            run_id="run-struggle",
            status="completed",
            output={"struggling": True},
        )
    )


async def test_corrective_retrieval_serves_reteach_with_on_topic_chunks(tmp_path: Path) -> None:
    """
    BDD Scenario #1
    ---------------
    Scenario: corrective retrieval serves the re-teach engagement with on-topic chunks

    Given a knowledge base seeded with chunks for a concept at two difficulty levels
    And an engagement whose outcome marks the subject as struggling
    When the struggle hook selects the easier engagement and it runs with retrieval
    Then the retrieved chunks are on-topic for the SAME concept being re-taught
    And the retrieval query reflects the re-teach context, not the original failed query verbatim
    """
    pack = load_domain_pack("coop-finance")

    # Given a knowledge base seeded with chunks for a concept at two difficulty levels
    #   (plus one unrelated chunk in the same KB that on-topic retrieval must not return)
    kb = CorpusKnowledgeBase(
        {
            pack.kb_names[0]: [
                ADVANCED_CERTIFICATE_CHUNK,
                FOUNDATIONAL_CERTIFICATE_CHUNK,
                UNRELATED_OVERDRAFT_CHUNK,
            ],
        }
    )
    memory = MemoryCore(schema=pack.schema, store=FileMemoryStore(path=tmp_path / "memory.json"))
    subject_id = uuid4()

    interaction = InteractionAgent(
        schema=pack.schema,
        kb=kb,
        memory=memory,
        model=TestModel(custom_output_text="Let's revisit share certificates from the basics."),
    )

    # And an engagement whose outcome marks the subject as struggling
    recorded_payloads: list[dict] = []

    async def record_after(context: HookContext) -> None:
        recorded_payloads.append(context.payload)

    hooks = HookRegistry()
    hooks.register(event=HookEvent.ON_STRUGGLE_DETECTED, fn=on_struggle)
    hooks.register(event=HookEvent.AFTER_ENGAGEMENT, fn=record_after)

    runner = _struggling_runner()
    orchestrator = EngagementOrchestrator(
        schema=pack.schema,
        runner=runner,
        memory=memory,
        skills=pack.skills,
        hooks=hooks,
    )

    # The failed turn: the learner asked for the advanced treatment and got it.
    await interaction.turn(subject_id, ORIGINAL_FAILED_QUERY)
    assert kb.results[0][0].text == ADVANCED_CERTIFICATE_CHUNK.text

    await orchestrator.run_engagement(
        skill_name="suggest-allocation",
        subject_id=subject_id,
        thread_id="thread-1",
    )

    # When the struggle hook selects the easier engagement...
    next_skill = recorded_payloads[0]["next_skill"]
    assert next_skill == "explain-product"

    # ...and it runs with retrieval — the re-teach query is derived from the
    # re-teach context (the easier engagement + the same concept), not replayed.
    reteach_query = f"{next_skill} re-teach: cover the basics of share certificates simply"
    await orchestrator.run_engagement(
        skill_name=next_skill,
        subject_id=subject_id,
        thread_id="thread-2",
    )
    await interaction.turn(subject_id, reteach_query)

    assert runner.requests[1].workflow_id == pack.skills.workflow_id(next_skill)

    # Then the retrieved chunks are on-topic for the SAME concept being re-taught
    reteach_chunks = kb.results[-1]
    assert reteach_chunks
    assert all("share certificate" in chunk.text.lower() for chunk in reteach_chunks)
    assert UNRELATED_OVERDRAFT_CHUNK.text not in [chunk.text for chunk in reteach_chunks]

    # ...and the simpler level leads: the foundational chunk outranks the
    # advanced one the learner just failed on.
    assert reteach_chunks[0].text == FOUNDATIONAL_CERTIFICATE_CHUNK.text

    # And the retrieval query reflects the re-teach context, not the original
    # failed query verbatim.
    assert [call[0] for call in kb.calls] == [ORIGINAL_FAILED_QUERY, reteach_query]
    assert reteach_query != ORIGINAL_FAILED_QUERY
    assert next_skill in reteach_query

    # Both retrievals hit the pack's KB, at the InteractionAgent's contract top_k.
    assert kb.calls[-1] == (reteach_query, list(pack.kb_names), 5)


async def test_adaptive_path_retrieves_from_the_education_pack_kb(tmp_path: Path) -> None:
    """
    BDD Scenario #2
    ---------------
    Scenario: the adaptive path retrieves from the correct per-domain KB

    Given the education pack loaded via load_domain_pack
    When the re-teach engagement retrieves
    Then the chunks come from the education KB named in the pack (no cross-domain bleed)
    """
    # Given the education pack loaded via load_domain_pack
    pack = load_domain_pack("education")

    # A corpus spanning BOTH domains' knowledge bases: the finance chunk is bait
    # that lexically matches the education re-teach query, so only KB routing —
    # not luck of the seeding — keeps it out.
    kb = CorpusKnowledgeBase(
        {
            "primer-education-kb": [FRACTIONS_FOUNDATIONS_CHUNK],
            "primer-coop-finance-kb": [FINANCE_BAIT_CHUNK],
        }
    )
    memory = MemoryCore(schema=pack.schema, store=FileMemoryStore(path=tmp_path / "memory.json"))
    subject_id = uuid4()

    recorded_payloads: list[dict] = []

    async def record_after(context: HookContext) -> None:
        recorded_payloads.append(context.payload)

    hooks = HookRegistry()
    hooks.register(event=HookEvent.ON_STRUGGLE_DETECTED, fn=on_struggle)
    hooks.register(event=HookEvent.AFTER_ENGAGEMENT, fn=record_after)

    orchestrator = EngagementOrchestrator(
        schema=pack.schema,
        runner=_struggling_runner(),
        memory=memory,
        skills=pack.skills,
        hooks=hooks,
    )

    # The learner struggles in tutor-concept. The education pack ships a single
    # real engagement, so the corrective path re-teaches through tutor-concept
    # itself: on_struggle has nothing simpler to select (the hook stays a no-op
    # at the schema's floor engagement) and the re-teach query carries the level.
    await orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=subject_id,
        thread_id="thread-1",
    )
    assert recorded_payloads[0]["struggling"] is True
    assert "next_skill" not in recorded_payloads[0]

    # When the re-teach engagement retrieves
    interaction = InteractionAgent(
        schema=pack.schema,
        kb=kb,
        memory=memory,
        model=TestModel(custom_output_text="A fraction names equal parts of a whole."),
    )
    reteach_query = "tutor-concept re-teach: cover the basics of fractions with one simple example"
    await interaction.turn(subject_id, reteach_query)

    # Then the chunks come from the education KB named in the pack...
    assert kb.calls == [(reteach_query, list(pack.kb_names), 5)]
    assert list(pack.kb_names) == ["primer-education-kb"]

    reteach_chunks = kb.results[-1]
    assert [chunk.text for chunk in reteach_chunks] == [FRACTIONS_FOUNDATIONS_CHUNK.text]

    # ...and the finance bait stayed out purely through KB routing: it shares
    # ranking tokens with the query (it would have been returned had the finance
    # KB been searched), yet it never reached the results.
    assert ranking_tokens(reteach_query) & ranking_tokens(FINANCE_BAIT_CHUNK.text)
    assert FINANCE_BAIT_CHUNK.text not in [chunk.text for chunk in reteach_chunks]
