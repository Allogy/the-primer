import json
import math
import os
from uuid import uuid4

from dotenv import load_dotenv
from openai import OpenAI

from capillary_actions_sdk.tutor import TutoringAgent
from capillary_actions_sdk.yaml_loader import load_bloom_policy, load_kg, load_modality_policy

load_dotenv()

# ---------------------------------------------------------------------------
# Client — swap model string here if you want a different one
# ---------------------------------------------------------------------------

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

MODEL = "openai/gpt-4o"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chat(system: str, messages: list[dict]) -> str:
    """Send a chat request and return the assistant's reply as a string."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, *messages],
        temperature=0.3,        # low temperature — we want consistent scoring
    )
    return response.choices[0].message.content.strip()

def _chat_json(system: str, messages: list[dict]) -> dict:
    """Same as _chat but parses the response as JSON.
    The system prompt must instruct the model to return only JSON.
    """
    raw = _chat(system, messages)
    # Strip accidental markdown fences the model sometimes adds
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(clean)

kg = load_kg("examples/kg/abstract_algebra.yaml")
bloom = load_bloom_policy("examples/policies/bloom.yaml")
modality = load_modality_policy("examples/policies/modality.yaml")

concept = kg.get("group")

agent = TutoringAgent(
    concept=concept,
    bloom_policy=bloom,
    modality_policy=modality,
    chat_fn=_chat,
    chat_json_fn=_chat_json
)

teaching = agent.teach()
print("\n=== TEACHING ===\n", teaching)

probe = agent.probe(teaching)
print("\n=== PROBE ===\n", probe)

response = input("\nYour answer: ")

print("\n=== RESPONSE ===\n", response)

result = agent.score(teaching, probe, response)

for rs in result.rubric_scores:
    bar = "█" * int(rs.score * 10) + "░" * (10 - int(rs.score * 10))
    print(f"  [{bar}] {rs.score:.2f}  {rs.criterion}")
    if rs.rationale:
        print(f"           → {rs.rationale}")

    print(f"\n  Overall score     : {result.score:.2f}")
    print(f"  Bloom demonstrated: {result.bloom_level_demonstrated.value}")
    print(f"  Passed            : {result.passed}")
    print(f"\n  Rationale: {result.agent_rationale}")
