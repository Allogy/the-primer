from uuid import UUID

import yaml

from capillary_actions_sdk.models.enums import AssessmentModality, BloomLevel
from capillary_actions_sdk.models.learner_interaction import KnowledgeConcept, KnowledgeGraph


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_bloom_policy(path: str) -> dict:
    return load_yaml(path)["bloom_levels"]

def load_modality_policy(path: str) -> dict:
    return load_yaml(path)["assessment_modalities"]

def load_kg(path: str) -> KnowledgeGraph:
    data = load_yaml(path)

    concepts = [
        KnowledgeConcept(
            id=c["id"],
            name=c["name"],
            description=c.get("description", ""),
            prerequisites=c.get("prerequisites", []),
            difficulty=c.get("difficulty", 1),
            tags=c.get("tags", []),
            bloom_level=BloomLevel[c["bloom_level"]],
            assessment_modality=AssessmentModality[c["assessment_modality"]],
            passing_threshold=c.get("passing_threshold", 0.7),
            mastery_criteria=c.get("mastery_criteria", []),
            misconceptions=c.get("misconceptions", []),
            decay_halflife_days=c.get("decay_halflife_days", 14),
            max_attempts=c.get("max_attempts", 3),
            estimated_minutes=c.get("estimated_minutes", 30),
        )
        for c in data["concepts"]
    ]

    return KnowledgeGraph(
        id=UUID(data["id"]),
        name=data["name"],
        description=data.get("description", ""),
        source=data.get("source", "yaml"),
        concepts=concepts,
    )
