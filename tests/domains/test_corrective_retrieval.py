"""Corrective retrieval quality around the struggle -> re-teach seam (KG-W4).

KG-W5 proved per-domain KB *wiring*; this story proves the *content* served to
a re-teach step. The engine deliberately ships no query-rewriting or handoff
component — turning the struggle hook's ``next_skill`` into a re-teach query
and issuing the retrieval turn is the demo driver's job — so these tests are
component-level coverage of the two sides of that seam, with the test itself
standing in as the demo driver for the handoff:

* the struggle hook's ``next_skill`` derivation (``on_struggle`` walking
  ``schema.engagements``), and
* the retrieval and KB routing that the re-teach step consumes
  (``InteractionAgent.turn`` against the pack's KB names).

Difficulty is a property of the seeded fixtures and the re-teach query, never of
the engine: chunks carry their level in their own text, and the corrective
retriever stand-in ranks by lexical overlap with the query, so every on-topic
assertion exercises the query and KB routing rather than echoing seed order.

Scenario 1 uses the coop-finance pack because the struggle hook derives the
easier engagement from ``schema.engagements`` and coop-finance is the pack that
ships more than one real engagement. The education pack ships a single real
engagement (plus the ``'...'`` placeholder), so its struggle hook must stay a
safe no-op at the floor — Scenario 2 proves that no-op fires, then covers the
pack's retrieval routing with one direct ``InteractionAgent`` turn (no second
engagement run).
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from capillary_actions_sdk.models.knowledge import RetrievedChunk
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
from tests.domains.fakes import CorpusKnowledgeBase, ranking_tokens

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
        "Share certificates basics, a beginner introduction: a share certificate locks "
        "savings for a fixed term and pays a set dividend."
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
    Scenario: corrective retrieval serves the re-teach step with on-topic chunks

    Given a knowledge base seeded with chunks for a concept at two difficulty levels
    And an engagement whose outcome marks the subject as struggling
    When the struggle hook selects the easier engagement
    And the test — acting as the demo driver — derives the re-teach query and retrieves
    Then the retrieved chunks are on-topic for the SAME concept being re-taught
    And the retrieval query reflects the re-teach context, not the original failed query verbatim

    Component-level coverage, not an end-to-end adaptive loop: the engine has no
    query-rewriting/handoff component (the demo driver owns it), so the hook ->
    retrieval handoff here is test-authored by design.
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

    # ...and the re-teach step runs with retrieval. The handoff is test-authored
    # (the engine has no query-rewriting component; the demo driver owns it):
    # the test derives the query from the hook's next_skill and the re-taught
    # concept, and issues the turn itself, standing in for the driver.
    reteach_query = (
        f"{next_skill} re-teach: a beginner introduction covering the basics of share certificates"
    )
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

    # Guard against fixture wording drift: the foundational-first ranking below
    # holds only while the re-teach query shares strictly more significant
    # tokens with the foundational chunk than with the advanced one. Compute
    # both overlaps with the same tokenizer the fake ranks by, and pin the
    # designed margin (3: basics/beginner/introduction beyond the shared
    # share/certificates) so any single-token drift fails HERE, loudly, instead
    # of silently flipping — or barely preserving — the ranking.
    reteach_tokens = ranking_tokens(reteach_query)
    foundational_overlap = len(reteach_tokens & ranking_tokens(FOUNDATIONAL_CERTIFICATE_CHUNK.text))
    advanced_overlap = len(reteach_tokens & ranking_tokens(ADVANCED_CERTIFICATE_CHUNK.text))
    assert foundational_overlap >= advanced_overlap + 3

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
    Scenario: re-teach retrieval routes to the education pack's own KB

    Given the education pack loaded via load_domain_pack
    When the struggle hook fires at the pack's floor engagement and no-ops
    And the re-teach step retrieves (one direct InteractionAgent turn — the test
        acts as the demo driver; no second engagement run happens)
    Then the chunks come from the education KB named in the pack (no cross-domain bleed)

    Component-level coverage of two things: the floor-level struggle hook is
    dispatched and selects nothing simpler, and the retrieval a re-teach step
    would consume searches only the education KB.
    """
    # Given the education pack loaded via load_domain_pack
    pack = load_domain_pack("education")

    # A corpus spanning BOTH domains' knowledge bases: the finance chunk is bait
    # that lexically matches the education re-teach query, so only KB routing —
    # not luck of the seeding — keeps it out. The bait is seeded under the
    # finance pack's manifest-declared KB name (not a hardcoded literal) so a
    # future manifest rename cannot silently defuse the no-bleed assertion by
    # parking the bait under a name nothing would ever search.
    finance_kb_name = load_domain_pack("coop-finance").kb_names[0]
    kb = CorpusKnowledgeBase(
        {
            "primer-education-kb": [FRACTIONS_FOUNDATIONS_CHUNK],
            finance_kb_name: [FINANCE_BAIT_CHUNK],
        }
    )
    memory = MemoryCore(schema=pack.schema, store=FileMemoryStore(path=tmp_path / "memory.json"))
    subject_id = uuid4()

    recorded_payloads: list[dict] = []

    async def record_after(context: HookContext) -> None:
        recorded_payloads.append(context.payload)

    # Recording wrapper delegating to the real on_struggle: `struggling` is
    # written by run_engagement itself before ON_STRUGGLE_DETECTED fires, so
    # without proof of dispatch the no-op assertions below would also pass if
    # the struggle event were never delivered at all.
    struggle_hook_engagements: list[str] = []

    async def recording_on_struggle(context: HookContext) -> None:
        struggle_hook_engagements.append(context.engagement)
        await on_struggle(context)

    hooks = HookRegistry()
    hooks.register(event=HookEvent.ON_STRUGGLE_DETECTED, fn=recording_on_struggle)
    hooks.register(event=HookEvent.AFTER_ENGAGEMENT, fn=record_after)

    orchestrator = EngagementOrchestrator(
        schema=pack.schema,
        runner=_struggling_runner(),
        memory=memory,
        skills=pack.skills,
        hooks=hooks,
    )

    # The learner struggles in tutor-concept. The education pack ships a single
    # real engagement, so on_struggle has nothing simpler to select and must
    # stay a safe no-op at the schema's floor engagement. No second
    # run_engagement happens in this test: any re-teach would go through
    # tutor-concept itself, and the direct InteractionAgent turn below stands
    # in for that re-teach step, with the query carrying the level.
    await orchestrator.run_engagement(
        skill_name="tutor-concept",
        subject_id=subject_id,
        thread_id="thread-1",
    )
    assert recorded_payloads[0]["struggling"] is True

    # The floor no-op, proven: the struggle hook really was dispatched — exactly
    # once, for tutor-concept — and still selected nothing simpler.
    assert struggle_hook_engagements == ["tutor-concept"]
    assert "next_skill" not in recorded_payloads[0]

    # When the re-teach step retrieves — one direct turn, issued by the test as
    # the demo driver
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
