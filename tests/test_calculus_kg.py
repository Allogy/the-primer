"""The bootstrapped calculus knowledge graph loads and is a valid DAG.

Content provenance: examples/kg/calculus_v1.yaml is machine-drafted from
OpenStax Calculus Volume 1 (CC BY-NC-SA 4.0) and awaits subject-expert
review; see the file header and docs/content/calculus-v1-ocw-crosswalk.yaml.
These tests gate structure, not pedagogy.
"""

from graphlib import TopologicalSorter
from pathlib import Path

from the_primer.loader import load_kg

KG_PATH = Path(__file__).parent.parent / "examples" / "kg" / "calculus_v1.yaml"


def test_calculus_kg_loads_with_45_concepts() -> None:
    kg = load_kg(str(KG_PATH))
    assert len(kg.concepts) == 45


def test_calculus_kg_has_unique_ids_and_known_prerequisites() -> None:
    kg = load_kg(str(KG_PATH))
    ids = [c.id for c in kg.concepts]
    assert len(ids) == len(set(ids))
    id_set = set(ids)
    for concept in kg.concepts:
        unknown = set(concept.prerequisites) - id_set
        assert not unknown, f"{concept.id} references unknown prerequisites: {unknown}"


def test_calculus_kg_prerequisites_form_a_dag() -> None:
    kg = load_kg(str(KG_PATH))
    graph = {c.id: set(c.prerequisites) for c in kg.concepts}
    order = list(TopologicalSorter(graph).static_order())
    assert len(order) == len(kg.concepts)
    assert order[0] == "functions-review"


def test_calculus_kg_every_concept_has_mastery_criteria() -> None:
    kg = load_kg(str(KG_PATH))
    for concept in kg.concepts:
        assert concept.mastery_criteria, f"{concept.id} has no mastery criteria"
