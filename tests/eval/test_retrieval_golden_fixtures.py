"""Golden retrieval fixtures for the eval harness (KG-W6).

These tests own the *fixture* side of the retrieval-quality leg: the golden
record at ``fixtures/retrieval_golden.json`` that LD-W6's ``precision_at_k``
scores. Scoring itself (the metric function, thresholds, the report) is
deliberately NOT here — that is LD-W6's harness. What is asserted here:

* the frozen shape — per-domain keys ``education`` / ``coop-finance``, each
  case carrying ``query`` / ``retrieved_ids`` / ``relevant_ids``;
* id traceability — every id resolves to an identifiable corpus chunk of the
  same domain (``RetrievedChunk`` has no id by frozen SDK contract, so the
  chunk→id mapping lives in the fixture layer; see ``fixtures/README.md``);
* honesty — ``retrieved_ids`` equals a live ``CorpusKnowledgeBase`` ranking
  run over a KB seeded with BOTH domains' corpora, so the golden ordering can
  never be hand-sorted optimism and cross-domain bleed would fail loudly;
* parity — one code path, parametrized over both domains: no domain-specific
  branch exists, and each domain retrieves only from its manifest-declared KB.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from capillary_actions_sdk.models.knowledge import RetrievedChunk

from primer_core.domains import load_domain_pack
from tests.domains.fakes import CorpusKnowledgeBase, ranking_tokens

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "retrieval_golden.json"

DOMAINS = ["education", "coop-finance"]

# InteractionAgent.turn's contract top_k — the golden orderings were produced
# at this depth and the honesty test below re-runs them at the same depth.
CONTRACT_TOP_K = 5

# Proposed scoring depth for precision_at_k (freeze with LD-W6): every case's
# top-PROPOSED_K ranking positions are exactly its relevant ids.
PROPOSED_K = 2


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def _both_domain_kb(fixture: dict) -> tuple[CorpusKnowledgeBase, dict[str, str]]:
    """One KB seeded with BOTH domains' corpora under their manifest KB names.

    Returns the KB and the text->id join map. Seeding both domains means every
    single-domain retrieval below proves routing, not a conveniently empty KB.
    """
    corpus_by_kb: dict[str, list[RetrievedChunk]] = {}
    text_to_id: dict[str, str] = {}
    for domain in DOMAINS:
        chunks = fixture[domain]["corpus"]
        corpus_by_kb[fixture[domain]["kb_name"]] = [
            RetrievedChunk(text=chunk["text"], score=chunk["score"]) for chunk in chunks
        ]
        for chunk in chunks:
            text_to_id[chunk["text"]] = chunk["id"]
    return CorpusKnowledgeBase(corpus_by_kb), text_to_id


def test_fixture_has_exactly_the_two_domain_keys() -> None:
    assert set(_fixture()) == set(DOMAINS)


@pytest.mark.parametrize("domain", DOMAINS)
def test_cases_carry_the_frozen_shape(domain: str) -> None:
    """Each case carries query / retrieved_ids / relevant_ids, all non-empty."""
    section = _fixture()[domain]
    assert section["cases"], f"{domain} must ship at least one golden case"
    for case in section["cases"]:
        assert set(case) == {"query", "retrieved_ids", "relevant_ids"}
        assert isinstance(case["query"], str) and case["query"]
        for key in ("retrieved_ids", "relevant_ids"):
            assert isinstance(case[key], list) and case[key]
            assert all(isinstance(chunk_id, str) for chunk_id in case[key])


@pytest.mark.parametrize("domain", DOMAINS)
def test_corpus_chunks_are_identifiable(domain: str) -> None:
    """Unique ids, unique join-key texts, and RetrievedChunk-valid text/score."""
    corpus = _fixture()[domain]["corpus"]
    ids = [chunk["id"] for chunk in corpus]
    texts = [chunk["text"] for chunk in corpus]
    assert len(set(ids)) == len(ids)
    assert len(set(texts)) == len(texts), "text is the chunk->id join key; it must be unique"
    for chunk in corpus:
        RetrievedChunk(text=chunk["text"], score=chunk["score"])  # validates score in [0, 1]


@pytest.mark.parametrize("domain", DOMAINS)
def test_ids_trace_back_to_the_domain_corpus(domain: str) -> None:
    """Every retrieved/relevant id resolves to a corpus chunk of the SAME domain."""
    section = _fixture()[domain]
    corpus_ids = {chunk["id"] for chunk in section["corpus"]}
    for case in section["cases"]:
        assert set(case["retrieved_ids"]) <= corpus_ids
        assert set(case["relevant_ids"]) <= corpus_ids


@pytest.mark.parametrize("domain", DOMAINS)
def test_kb_name_matches_the_manifest(domain: str) -> None:
    """The golden record states the KB name the domain pack actually declares."""
    assert [_fixture()[domain]["kb_name"]] == list(load_domain_pack(domain).kb_names)


@pytest.mark.parametrize("domain", DOMAINS)
async def test_retrieved_ids_are_a_live_ranking_run(domain: str) -> None:
    """The golden ordering reproduces from the real ranking — never hand-sorted.

    The KB holds BOTH domains' corpora; retrieval routes only the case's own
    manifest KB, so equality with the golden ids also proves no cross-domain
    bleed (every golden id belongs to this domain's corpus).
    """
    fixture = _fixture()
    kb, text_to_id = _both_domain_kb(fixture)
    kb_names = list(load_domain_pack(domain).kb_names)

    for case in fixture[domain]["cases"]:
        retrieved = await kb.retrieve(case["query"], kb_names, top_k=CONTRACT_TOP_K)
        assert [text_to_id[chunk.text] for chunk in retrieved] == case["retrieved_ids"]


@pytest.mark.parametrize("domain", DOMAINS)
async def test_no_bleed_is_proven_by_bait_not_by_luck(domain: str) -> None:
    """Widen routing to ALL KBs and a foreign chunk reaches every case's top-k.

    Without this, the no-bleed half of the live-ranking test would be vacuous:
    routing would be the only excluder of nothing. Token overlap alone is not
    enough — an overlapping foreign chunk could still sit below top_k. So probe
    each query across BOTH domains' KBs and require an other-domain chunk
    inside the contract top_k: single-domain routing is then provably the only
    thing keeping it out of the golden results.
    """
    fixture = _fixture()
    kb, text_to_id = _both_domain_kb(fixture)
    all_kb_names = [fixture[d]["kb_name"] for d in DOMAINS]
    own_ids = {chunk["id"] for chunk in fixture[domain]["corpus"]}

    for case in fixture[domain]["cases"]:
        retrieved = await kb.retrieve(case["query"], all_kb_names, top_k=CONTRACT_TOP_K)
        retrieved_ids = {text_to_id[chunk.text] for chunk in retrieved}
        assert retrieved_ids - own_ids, (
            f"no other-domain chunk reaches top-{CONTRACT_TOP_K} for {case['query']!r}; "
            "the no-bleed proof would be vacuous"
        )


def test_ids_and_texts_are_unique_file_wide() -> None:
    """The chunk->id join map spans BOTH domains, so uniqueness must too.

    Per-domain uniqueness is not enough: a text duplicated across domains would
    corrupt the merged text->id map and fail the live-ranking test with a
    cryptic wrong-id mismatch instead of a clear message here.
    """
    fixture = _fixture()
    ids = [chunk["id"] for domain in DOMAINS for chunk in fixture[domain]["corpus"]]
    texts = [chunk["text"] for domain in DOMAINS for chunk in fixture[domain]["corpus"]]
    assert len(set(ids)) == len(ids)
    assert len(set(texts)) == len(texts)


@pytest.mark.parametrize("domain", DOMAINS)
def test_ranking_keys_are_tie_free(domain: str) -> None:
    """No two candidates share a (token-overlap, score) rank key for any case.

    CorpusKnowledgeBase breaks exact rank-key ties by Python's stable sort —
    i.e. corpus seed order. The golden orderings must never depend on that:
    every candidate a query actually ranks must differ in overlap or score, so
    reordering the corpus can never silently change retrieved_ids.
    """
    section = _fixture()[domain]
    for case in section["cases"]:
        query_tokens = ranking_tokens(case["query"])
        keys = [
            (len(query_tokens & ranking_tokens(chunk["text"])), chunk["score"])
            for chunk in section["corpus"]
            if query_tokens & ranking_tokens(chunk["text"])
        ]
        assert len(set(keys)) == len(keys), f"rank-key tie for query {case['query']!r}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_relevant_ids_lead_the_ranking(domain: str) -> None:
    """Fixture self-check: a perfect precision@PROPOSED_K is attainable.

    The top-PROPOSED_K retrieved ids are exactly the relevant set, for every
    case, through this one domain-agnostic code path. The scoring itself
    (precision_at_k, thresholds, the report) belongs to LD-W6.
    """
    for case in _fixture()[domain]["cases"]:
        assert len(case["relevant_ids"]) == PROPOSED_K
        assert set(case["retrieved_ids"][:PROPOSED_K]) == set(case["relevant_ids"])
