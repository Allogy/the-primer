"""Tests for primer_core.interaction.InteractionAgent."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from capillary_actions_sdk.models.knowledge import RetrievedChunk
from pydantic_ai import capture_run_messages
from pydantic_ai.models.test import TestModel

from primer_core.interaction import InteractionAgent
from primer_core.testing.fakes import FakeKnowledgeBase


class RecordingMemory:
    """Minimal memory fake that records working-memory requests."""

    def __init__(self) -> None:
        self.subject_ids: list[UUID] = []

    async def assemble_working_memory(
        self,
        subject_id: UUID,
    ) -> SimpleNamespace:
        self.subject_ids.append(subject_id)

        return SimpleNamespace(
            learner_id=subject_id,
            entries=["Learner previously completed calculus."],
        )


def _education_schema() -> SimpleNamespace:
    """Create the schema shape required by InteractionAgent."""
    return SimpleNamespace(
        knowledge_base=SimpleNamespace(
            kb_names=["primer-education-kb"],
        )
    )


def _captured_text(messages: list[Any]) -> str:
    """Collect string content from captured Pydantic AI messages."""
    text_parts: list[str] = []

    for message in messages:
        for part in message.parts:
            content = getattr(part, "content", None)

            if isinstance(content, str):
                text_parts.append(content)

    return "\n".join(text_parts)


class TestInteractionAgent:
    async def test_turn_uses_rag_and_returns_model_output(self) -> None:
        subject_id = uuid4()

        chunk = RetrievedChunk(
            text="A derivative measures instantaneous rate of change.",
            score=0.95,
        )
        kb = FakeKnowledgeBase([chunk])
        memory = RecordingMemory()
        model = TestModel(custom_output_text="Derivatives describe rates of change.")

        agent = InteractionAgent(
            schema=_education_schema(),
            kb=kb,
            memory=memory,
            model=model,
        )

        with capture_run_messages() as messages:
            result = await agent.turn(
                subject_id,
                "teach me derivatives",
            )

        assert result == "Derivatives describe rates of change."

        assert kb.calls == [
            (
                "teach me derivatives",
                ["primer-education-kb"],
                5,
            )
        ]

        assert memory.subject_ids == [subject_id]

        prompt_text = _captured_text(messages)

        assert "teach me derivatives" in prompt_text
        assert "A derivative measures instantaneous rate of change." in prompt_text
        assert "Learner previously completed calculus." in prompt_text
