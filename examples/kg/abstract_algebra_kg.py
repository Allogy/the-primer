"""Test fixture — Abstract Algebra knowledge graph (hand-authored).

Six concepts covering the path from Set Theory -> Group -> Subgroup -> Cosets.
Designed to exercise all three gate decisions: pass, retry, escalate.
"""

from __future__ import annotations

from uuid import UUID

from capillary_actions_sdk.models.enums import AssessmentModality, BloomLevel
from capillary_actions_sdk.models.learner_interaction import KnowledgeConcept, KnowledgeGraph

ABSTRACT_ALGEBRA_KG = KnowledgeGraph(
    id=UUID("00000000-0000-0000-0000-000000000001"),
    name="Abstract Algebra — Foundations",
    description="Core group theory concepts from set-theoretic prerequisites to quotient groups.",
    source="hand-authored",
    concepts=[

        # ── Tier 0: prerequisites ─────────────────────────────────────────

        KnowledgeConcept(
            id="set-theory",
            name="Set Theory Basics",
            description=(
                "Sets, elements, subsets, union, intersection, and Cartesian product. "
                "The language all algebraic structures are built on."
            ),
            prerequisites=[],
            difficulty=1,
            tags=["foundations", "logic"],
            bloom_level=BloomLevel.remember,
            assessment_modality=AssessmentModality.recall,
            passing_threshold=0.70,
            mastery_criteria=[
                "Can define a set and identify elements",
                "Can compute union, intersection, and Cartesian product",
                "Can distinguish subset from proper subset",
            ],
            misconceptions=[
                "Confusing the empty set ∅ with {∅}",
                "Treating {1, 2} and {2, 1} as different sets",
            ],
            decay_halflife_days=28,
            max_attempts=3,
            estimated_minutes=15,
        ),

        KnowledgeConcept(
            id="binary-operations",
            name="Binary Operations",
            description=(
                "A binary operation on a set S is a function S × S → S. "
                "Closure, commutativity, associativity, identity, and inverses."
            ),
            prerequisites=["set-theory"],
            difficulty=2,
            tags=["foundations", "operations"],
            bloom_level=BloomLevel.understand,
            assessment_modality=AssessmentModality.explanation,
            passing_threshold=0.72,
            mastery_criteria=[
                "Can explain what closure means and verify it for an example",
                "Can distinguish commutative from non-commutative operations",
                "Can identify identity element and inverses",
            ],
            misconceptions=[
                "Assuming all binary operations are commutative",
                "Confusing the identity element with zero",
            ],
            decay_halflife_days=21,
            max_attempts=3,
            estimated_minutes=20,
        ),

        # ── Tier 1: core structure ────────────────────────────────────────

        KnowledgeConcept(
            id="group",
            name="Group",
            description=(
                "A group (G, ·) is a set with a binary operation satisfying "
                "closure, associativity, identity, and inverses. "
                "The central object of abstract algebra."
            ),
            prerequisites=["set-theory", "binary-operations"],
            difficulty=3,
            tags=["core", "group-theory"],
            bloom_level=BloomLevel.understand,
            assessment_modality=AssessmentModality.explanation,
            passing_threshold=0.75,
            mastery_criteria=[
                "Can state all four group axioms from memory",
                "Can verify whether a given structure is a group",
                "Can give two examples of groups (e.g. ℤ under +, S₃)",
                "Can explain why (ℕ, +) is not a group",
            ],
            misconceptions=[
                "Assuming groups must be commutative (confusing group with abelian group)",
                "Forgetting that inverses must exist for every element",
                "Thinking the identity element must be 0 or 1",
            ],
            decay_halflife_days=14,
            max_attempts=3,
            estimated_minutes=30,
        ),

        # ── Tier 2: derived structures ────────────────────────────────────

        KnowledgeConcept(
            id="subgroup",
            name="Subgroup",
            description=(
                "A subgroup H of G is a non-empty subset closed under the group "
                "operation and inverses. The subgroup test provides a two-condition shortcut."
            ),
            prerequisites=["group"],
            difficulty=3,
            tags=["group-theory", "substructures"],
            bloom_level=BloomLevel.apply,
            assessment_modality=AssessmentModality.application,
            passing_threshold=0.75,
            mastery_criteria=[
                "Can state and apply the one-step subgroup test",
                "Can verify 2ℤ is a subgroup of (ℤ, +)",
                "Can identify a subset that fails the subgroup test and name which condition fails",
            ],
            misconceptions=[
                "Assuming every subset of a group is a subgroup",
                "Forgetting to check closure under inverses",
            ],
            decay_halflife_days=14,
            max_attempts=3,
            estimated_minutes=25,
        ),

        KnowledgeConcept(
            id="cosets",
            name="Cosets",
            description=(
                "For H ≤ G and g ∈ G, the left coset gH = {gh : h ∈ H}. "
                "Cosets partition the group; this leads directly to Lagrange's theorem."
            ),
            prerequisites=["subgroup"],
            difficulty=4,
            tags=["group-theory", "cosets"],
            bloom_level=BloomLevel.apply,
            assessment_modality=AssessmentModality.application,
            passing_threshold=0.75,
            mastery_criteria=[
                "Can compute left and right cosets of a given subgroup",
                "Can verify cosets partition the group",
                "Can state Lagrange's theorem and apply it to find |H| from |G|",
            ],
            misconceptions=[
                "Assuming left cosets always equal right cosets",
                "Treating cosets as subgroups",
            ],
            decay_halflife_days=14,
            max_attempts=3,
            estimated_minutes=30,
        ),

        KnowledgeConcept(
            id="homomorphism",
            name="Group Homomorphism",
            description=(
                "A homomorphism φ: G → H satisfies φ(ab) = φ(a)φ(b). "
                "The kernel and image are key invariants; isomorphisms are bijective homomorphisms."
            ),
            prerequisites=["group", "subgroup"],
            difficulty=4,
            tags=["group-theory", "maps"],
            bloom_level=BloomLevel.analyze,
            assessment_modality=AssessmentModality.application,
            passing_threshold=0.78,
            mastery_criteria=[
                "Can verify a map is a homomorphism",
                "Can compute the kernel and image of a homomorphism",
                "Can determine whether a homomorphism is an isomorphism",
                "Can explain why the kernel is always a normal subgroup",
            ],
            misconceptions=[
                "Thinking every homomorphism is an isomorphism",
                "Confusing the kernel with the identity element",
            ],
            decay_halflife_days=10,
            max_attempts=4,
            estimated_minutes=40,
        ),
    ],
)
