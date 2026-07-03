"""Workflow orchestration for registered Primer engagements."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from capillary_actions_sdk.ports.platform import (
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)

from primer_core.skills import SkillRegistry

if TYPE_CHECKING:
    from capillary_actions_sdk.schema import DomainSchema

    from primer_core.memory import MemoryCore


class EngagementOrchestrator:
    """Resolve registered skills and delegate execution to the workflow runner."""

    def __init__(
        self,
        schema: DomainSchema,
        runner: RunWorkflowPort,
        memory: MemoryCore,
        skills: SkillRegistry,
    ) -> None:
        self.schema = schema
        self.runner = runner
        self.memory = memory
        self.skills = skills

    async def run_engagement(
        self,
        skill_name: str,
        subject_id: UUID,
        thread_id: str,
        input_data: dict[str, Any] | None = None,
    ) -> RunWorkflowResponse:
        """Run a registered engagement and return its workflow response."""
        workflow_id = self.skills.workflow_id(skill_name)

        request = RunWorkflowRequest(
            workflow_id=workflow_id,
            thread_id=thread_id,
            input_data={} if input_data is None else input_data,
            org_id=None,
        )

        return await self.runner.run_sync(request)
