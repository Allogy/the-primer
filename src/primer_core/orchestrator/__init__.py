"""Workflow orchestration and lifecycle hooks."""

from primer_core.orchestrator.engagement import EngagementOrchestrator
from primer_core.orchestrator.hooks import HookContext, HookEvent, HookRegistry
from primer_core.orchestrator.triggers import TriggerScheduler
from primer_core.orchestrator.writeback import on_struggle, write_back_outcome

__all__ = [
    "EngagementOrchestrator",
    "HookContext",
    "HookEvent",
    "HookRegistry",
    "TriggerScheduler",
    "on_struggle",
    "write_back_outcome",
]
