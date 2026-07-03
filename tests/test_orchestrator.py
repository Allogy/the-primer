"""Tests for primer_core.orchestrator.EngagementOrchestrator."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from capillary_actions_sdk.ports.platform import RunWorkflowResponse

from primer_core.orchestrator import EngagementOrchestrator
from primer_core.skills import SkillRegistry
from primer_core.testing.fakes import FakeRunWorkflowPort


@pytest.fixture
def skills(tmp_path: Path) -> SkillRegistry:
    """Create a registry containing the tutor-concept skill."""
    wdf_path = tmp_path / "tutor-concept.yaml"
    wdf_path.write_text(
        yaml.safe_dump(
            {
                "name": "tutor-concept",
                "entry": "explain",
                "exit": "complete",
                "nodes": {
                    "explain": {},
                    "complete": {},
                },
            }
        ),
        encoding="utf-8",
    )

    registry = SkillRegistry()
    registry.register("tutor-concept", str(wdf_path))
    return registry


@pytest.fixture
def response() -> RunWorkflowResponse:
    """Create the canned response returned by the fake runner."""
    return RunWorkflowResponse(
        run_id="run-123",
        output={"result": "success"},
        status="completed",
    )


@pytest.fixture
def runner(response: RunWorkflowResponse) -> FakeRunWorkflowPort:
    """Create a workflow runner with a canned response."""
    return FakeRunWorkflowPort(response)


@pytest.fixture
def orchestrator(
    skills: SkillRegistry,
    runner: FakeRunWorkflowPort,
) -> EngagementOrchestrator:
    """Create an orchestrator with inert schema and memory dependencies."""
    return EngagementOrchestrator(
        schema=object(),
        runner=runner,
        memory=object(),
        skills=skills,
    )


class TestEngagementOrchestrator:
    async def test_runs_registered_engagement(
        self,
        orchestrator: EngagementOrchestrator,
        runner: FakeRunWorkflowPort,
        skills: SkillRegistry,
        response: RunWorkflowResponse,
    ) -> None:
        subject_id = uuid4()

        result = await orchestrator.run_engagement(
            "tutor-concept",
            subject_id,
            "thread-123",
            input_data={"concept": "limits"},
        )

        assert result is response
        assert len(runner.requests) == 1

        request = runner.requests[0]

        assert request.workflow_id == skills.workflow_id("tutor-concept")
        assert request.thread_id == "thread-123"
        assert request.input_data == {"concept": "limits"}
        assert request.org_id is None

    async def test_input_data_defaults_to_empty_dictionary(
        self,
        orchestrator: EngagementOrchestrator,
        runner: FakeRunWorkflowPort,
    ) -> None:
        await orchestrator.run_engagement(
            "tutor-concept",
            uuid4(),
            "thread-123",
        )

        assert runner.requests[0].input_data == {}

    async def test_unregistered_skill_raises_key_error(
        self,
        orchestrator: EngagementOrchestrator,
        runner: FakeRunWorkflowPort,
    ) -> None:
        with pytest.raises(KeyError):
            await orchestrator.run_engagement(
                "unknown-skill",
                uuid4(),
                "thread-123",
            )

        assert runner.requests == []
