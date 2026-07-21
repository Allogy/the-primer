"""Workflow orchestration for registered Primer engagements."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any
from uuid import UUID

from capillary_actions_sdk.events import AGUIEvent
from capillary_actions_sdk.ports.platform import (
    EventStreamPort,
    RunWorkflowPort,
    RunWorkflowRequest,
    RunWorkflowResponse,
)

from primer_core.orchestrator.hooks import HookContext, HookEvent, HookRegistry
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
        hooks: HookRegistry | None = None,
    ) -> None:
        self.schema = schema
        self.runner = runner
        self.memory = memory
        self.skills = skills
        self.hooks = hooks

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

        context = None
        if self.hooks is not None:
            context = HookContext(
                subject_id=subject_id,
                schema=self.schema,
                engagement=skill_name,
                payload={"input": request.input_data},
                memory=self.memory,
            )

            await self.hooks.fire(
                HookEvent.BEFORE_ENGAGEMENT,
                context,
            )

        response = await self.runner.run_sync(request)

        if self.hooks is not None and context is not None:
            context.payload["outcome"] = response.output
            context.payload["status"] = response.status
            context.payload["run_id"] = response.run_id

            await self.hooks.fire(
                HookEvent.AFTER_ENGAGEMENT,
                context,
            )

        return response

    async def run_engagement_streaming(
        self,
        skill_name: str,
        subject_id: UUID,
        thread_id: str,
        input_data: dict | None = None,
        event_stream: EventStreamPort | None = None,
    ) -> AsyncIterator[AGUIEvent]:
        """Run an engagement while yielding typed workflow events."""
        workflow_id = self.skills.workflow_id(skill_name)

        request = RunWorkflowRequest(
            workflow_id=workflow_id,
            thread_id=thread_id,
            input_data=input_data or {},
            org_id=None,
        )

        context = None

        if self.hooks is not None:
            context = HookContext(
                subject_id=subject_id,
                schema=self.schema,
                engagement=skill_name,
                payload={"input": request.input_data},
                memory=self.memory,
            )

            await self.hooks.fire(
                HookEvent.BEFORE_ENGAGEMENT,
                context,
            )

        events = self.runner.run(request)
        streamed_events: list[AGUIEvent] = []

        async for event in events:
            streamed_events.append(event)

            if event_stream is not None:
                await event_stream.send_event(event)

            yield event

        if self.hooks is not None and context is not None:
            context.payload["outcome"] = streamed_events

            await self.hooks.fire(
                HookEvent.AFTER_ENGAGEMENT,
                context,
            )
