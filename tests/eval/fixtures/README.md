# Retrieval golden fixtures (KG-W6)

`retrieval_golden.json` is the golden record the LD-W6 eval harness scores with
`precision_at_k(retrieved: list[dict], relevant_ids: set[str], k: int) -> float`.

## Shape

Top-level keys are exactly the two domain-pack names — `education` and
`coop-finance` (hyphen, matching `load_domain_pack`). Each domain carries:

| Key | Meaning |
|---|---|
| `kb_name` | The domain's manifest-declared KB name. Stated literally here because this file is the golden record; code must keep deriving it via `load_domain_pack(...).kb_names`. |
| `corpus` | The seeded chunks, each `{id, text, score}`. `text`/`score` are a valid `RetrievedChunk`; `id` exists only in this fixture layer (see below). |
| `cases` | The golden cases, each `{query, retrieved_ids, relevant_ids}`. |

## Chunk → id convention

`RetrievedChunk` has no `id` field (frozen SDK contract — `.text`/`.score`
only), so identity lives here in the fixture layer:

- Every corpus chunk gets a stable id: `{domain-prefix}-{content-slug}`, with
  prefixes `edu-` / `fin-` (e.g. `fin-share-certificate-basics`).
- Ids are unique across the whole file, and chunk **text is unique per domain**
  — the text is the join key that maps a retrieved `RetrievedChunk` back to its
  fixture id.
- Consumers that need id-bearing dicts build them as
  `{"id": <fixture id>, **chunk}` by matching on text.

## How `retrieved_ids` was produced (and is kept honest)

`retrieved_ids` is the output of a **live ranking run** of the shared
`CorpusKnowledgeBase` fake (`tests/domains/fakes.py`) — lexical token-overlap
ranking, score as tiebreak — with BOTH domains' corpora seeded under their
manifest KB names and only the case's own domain routed, at the
`InteractionAgent` contract `top_k=5`. It is not hand-sorted.

`tests/eval/test_retrieval_golden_fixtures.py` re-runs that exact ranking and
asserts equality, so any drift between this file and the ranking behaviour
fails CI loudly. Lists may be shorter than 5: zero-overlap chunks are filtered,
which is why each domain's high-score distractor chunk stays out of most cases.

## Proposed scoring parameters (freeze with LD-W6)

- **k = 2** — every case's top-2 equals its `relevant_ids`, so the expected
  score is exactly 1.0 per case.
- **threshold = 1.0** — the ranking is deterministic and fake-backed; anything
  below perfect is a real regression, not noise.

The fixture self-check `test_relevant_ids_lead_the_ranking` guarantees the
threshold is attainable at k=2. A perfect score is a **rank-regression check
over the deterministic fake**, not independent evidence of semantic relevance —
the corrective-retrieval quality claim it protects was established
functionally in KG-W4 (`tests/domains/test_corrective_retrieval.py`).

## Consumer notes (LD-W6)

- `relevant_ids` deserializes as a `list` — call `set(case["relevant_ids"])`
  for the frozen `precision_at_k` signature.
- To score a retrieval run: run it, **preserve the returned order**, and wrap
  each chunk into an id-bearing dict via the text join key, e.g.
  `{"id": text_to_id[chunk.text], "text": chunk.text, "score": chunk.score}`.
- Do **not** score the static `retrieved_ids` list as the system output — it is
  the golden expectation the run is compared against, not the measurement.

Queries speak the product vocabulary of the
merged WDFs (`explain-product`, `suggest-allocation`, `assess-readiness`
retrieval prompts) on the finance side; the education `tutor-concept` WDF is a
stub with no retrieval query text, so education cases use the established
test-corpus vocabulary (fractions, derivatives, limits) in the same
re-teach-query style as `tests/domains/test_corrective_retrieval.py` (KG-W4).
