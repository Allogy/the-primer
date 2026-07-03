"""RAG-backed learner interaction agent."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic_ai import Agent
from pydantic_ai.models import Model

if TYPE_CHECKING:
    from capillary_actions_sdk.ports.knowledge import KnowledgeBasePort
    from capillary_actions_sdk.schema import DomainSchema

    from primer_core.memory import MemoryCore


class InteractionAgent:
    """Generate learner-facing responses using retrieval and working memory."""

    def __init__(
        self,
        schema: DomainSchema,
        kb: KnowledgeBasePort,
        memory: MemoryCore,
        model: Model | None = None,
    ) -> None:
        self.schema = schema
        self.kb = kb
        self.memory = memory
        self.agent = Agent(
            model=model,
            output_type=str,
        )

    async def turn(
        self,
        subject_id: UUID,
        user_input: str,
    ) -> str:
        """Produce one interaction turn using KB and learner-memory context."""
        kb_names = list(self.schema.knowledge_base.kb_names)

        chunks = await self.kb.retrieve(
            user_input,
            kb_names,
            top_k=5,
        )

        working_memory = await self.memory.assemble_working_memory(subject_id)

        knowledge_context = "\n".join(chunk.text for chunk in chunks)
        memory_context = "\n".join(str(entry) for entry in working_memory.entries)

        prompt = (
            f"User request:\n{user_input}\n\n"
            f"Retrieved knowledge:\n{knowledge_context}\n\n"
            f"Learner working memory:\n{memory_context}"
        )

        result = await self.agent.run(prompt)

        return result.output
