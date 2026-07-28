"""Reserved module path for coop-finance domain models — DS-W5 (Joseph).

Nothing is defined here yet, deliberately. KG-W5 (RAG-1847) fixes the import
path so DS-W5 can land the model without touching the pack wiring or any
engine module.

Expected DS-W5 deliverable::

    class AllocationSuggestion(BaseModel):
        recommendation: str   # the product or split being recommended
        rationale: str        # member-facing explanation, grounded in retrieved chunks
        confidence: float     # 0.0-1.0

It is the structured output contract of the `suggest-allocation` engagement
(see wdf/suggest-allocation.workflow.yaml). No placeholder class is provided,
so an early import of a half-built model fails loudly rather than silently
type-checking against a stub.
"""

from __future__ import annotations
