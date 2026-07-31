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

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "AllocationSuggestion",
    "derive_confidence",
    "profile_completeness",
]

CONFIDENCE_FLOOR = 0.10
EVIDENCE_WEIGHT = 0.60
PROFILE_WEIGHT = 0.30
EVIDENCE_SATURATION = 4
CONFIDENCE_PRECISION = 3


class AllocationSuggestion(BaseModel):
    """A structured allocation recommendation grounded in finance-KB evidence.

    The recommendation states what the member should consider, while the
    rationale explains why using retrieved evidence. Source identifiers remain
    in the engagement outcome under ``suggestion_sources`` so this model
    preserves the required three-field contract.

    Confidence measures the amount of retrieved evidence and available member
    context. It is computed by :func:`derive_confidence`, not reported by the
    language model.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("recommendation", "rationale")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        """Strip surrounding whitespace and reject blank text."""

        value = value.strip()
        if not value:
            raise ValueError("must not be blank or whitespace-only")
        return value

    @classmethod
    def from_outcome_output(
        cls,
        output: Mapping[str, Any],
    ) -> AllocationSuggestion:
        """Validate the suggestion stored in an engagement output."""

        try:
            payload = output["suggestion"]
        except KeyError as exc:
            raise ValueError("engagement output does not contain a 'suggestion' key") from exc

        if not isinstance(payload, Mapping):
            raise ValueError(
                f"output['suggestion'] must be a mapping, got {type(payload).__name__}"
            )

        return cls.model_validate(payload)


def derive_confidence(
    *,
    retrieved_passage_count: int,
    profile_completeness: float,
) -> float:
    """Compute a deterministic confidence score from evidence and context.

    The score consists of:

    - a 0.10 floor when a suggestion is produced;
    - up to 0.60 for retrieved evidence, saturating at four passages;
    - up to 0.30 for member-profile completeness.

    This initial heuristic measures evidence breadth rather than relevance.
    Its weights are fixed for deterministic comparison and are not empirically
    calibrated.

    Raises:
        ValueError: If the passage count is negative or profile completeness
            falls outside the inclusive range 0.0 to 1.0.
    """

    if retrieved_passage_count < 0:
        raise ValueError("retrieved_passage_count must be >= 0")

    if not 0.0 <= profile_completeness <= 1.0:
        raise ValueError("profile_completeness must be between 0.0 and 1.0")

    evidence_fraction = min(retrieved_passage_count, EVIDENCE_SATURATION) / EVIDENCE_SATURATION

    score = (
        CONFIDENCE_FLOOR
        + EVIDENCE_WEIGHT * evidence_fraction
        + PROFILE_WEIGHT * profile_completeness
    )

    return round(min(score, 1.0), CONFIDENCE_PRECISION)


def profile_completeness(
    populated_dimensions: Sequence[str],
    expected_dimensions: Sequence[str],
) -> float:
    """Return the fraction of expected dimensions that are populated."""

    expected = set(expected_dimensions)
    if not expected:
        return 0.0

    populated = set(populated_dimensions)
    completeness = len(populated & expected) / len(expected)

    return round(completeness, CONFIDENCE_PRECISION)
