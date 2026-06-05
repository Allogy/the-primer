from typing import Any, Callable, Dict
from uuid import UUID, uuid4

from capillary_actions_sdk.models.enums import BloomLevel
from capillary_actions_sdk.models.learner_interaction import AssessmentResult, KnowledgeConcept, RubricScore


class TutoringAgent:
    def __init__(self,
                 concept: KnowledgeConcept, bloom_policy: Dict[str, Any],
                 modality_policy: Dict[str, Any],
                 chat_fn: Callable[[str, list[dict]], str],
                 chat_json_fn: Callable[[str, list[dict]], dict],
                 session_id: UUID | None = None,
                ):
        self.concept = concept
        self.bloom_policy = bloom_policy
        self.modality_policy = modality_policy
        self.chat = chat_fn
        self.chat_json = chat_json_fn
        self.session_id = session_id or uuid4()

    def teach(self):
        c = self.concept
        bloom = self.bloom_policy[c.bloom_level.value]["teaching"]

        system = f"""
You are a tutor.

Concept: {c.name}

Teaching rule: {bloom}

Misconceptions:
- {chr(10).join(c.misconceptions)}
"""
        
        return self.chat(system, [
            {"role": "user", "content": f"Teach me {c.name}"}
        ])
    
    def probe(self, teaching: str):
        c = self.concept
        probe_rule = self.bloom_policy[c.bloom_level.value]["probe"]
        modality = self.modality_policy[c.assessment_modality.value]["context"]

        system = f"""
Generate ONE question.

Probe rule: {probe_rule}

Modality: {modality}

Must test: {chr(10).join(c.mastery_criteria)}
"""
        
        return self.chat(system, [
            {"role": "assistant", "content": teaching},
            {"role": "user", "content": "Test me"}
        ])
    
    def score(self, teaching: str, probe: str, student_response: str) -> AssessmentResult:
        c = self.concept

        bloom_levels = " < ".join(b.value for b in BloomLevel)

        system = f"""
You are an expert assessor for the concept: {c.name}.

Concept Bloom target: {c.bloom_level.value}
Passing threshold: {c.passing_threshold}

Mastery criteria:
{chr(10).join(f'- {crit}' for crit in c.mastery_criteria)}

Bloom levels (ordered):
{bloom_levels}

You MUST respond with ONLY valid JSON — no markdown, no prose outside the JSON.
Schema:
{{
  "rubric_scores": [
    {{
      "criterion": "<exact criterion text>",
      "score": <float 0.0-1.0>,
      "rationale": "<one sentence explaining the score>"
    }}
  ],
  "bloom_level_demonstrated": "<one of: remember|understand|apply|analyze|evaluate|create>",
  "overall_rationale": "<two sentences: what the student showed and what is missing>"
}}
 
Be strict. A student who recites a memorised definition has demonstrated 'remember', not 'understand'.
A student who applies a procedure correctly to a novel case has demonstrated 'apply'."""
        
        messages = [
            {"role": "assistant", "content": teaching},
            {"role": "user",      "content": probe},
            {"role": "assistant", "content": "Please go ahead with your response."},
            {"role": "user",      "content": student_response},
        ]

        raw = self.chat_json(system, messages)

        rubric_scores = [
            RubricScore(
                criterion=r["criterion"],
                score=float(r["score"]),
                rationale=r.get("rationale"),
            )
            for r in raw["rubric_scores"]
        ]

        # Weighted average (equal weights for PoC — can be weighted later)
        overall_score = (
            sum(r.score for r in rubric_scores) / len(rubric_scores)
            if rubric_scores else 0.0
        )

        bloom_demonstrated = BloomLevel(raw["bloom_level_demonstrated"])
        passed = overall_score >= c.passing_threshold

        return AssessmentResult(
            id=uuid4(),
            engagement_id=self.session_id,
            learner_id=uuid4(),          # in a real system, pass the learner UUID in
            concept_id=c.id,
            target_bloom_level=c.bloom_level,
            target_modality=c.assessment_modality,
            bloom_level_demonstrated=bloom_demonstrated,
            rubric_scores=rubric_scores,
            score=overall_score,
            passed=passed,
            agent_rationale=raw.get("overall_rationale"),
        )

