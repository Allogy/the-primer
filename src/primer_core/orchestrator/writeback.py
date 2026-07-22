"""Reference handlers for writing engagement outcomes to memory."""

from uuid import UUID, uuid4

from capillary_actions_sdk.models.student_model import PreferenceSignal

from primer_core.orchestrator.hooks import HookContext

SENTINEL_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")


async def write_back_outcome(ctx: HookContext) -> None:
    """Persist a completed engagement outcome to learner memory."""
    outcome = ctx.payload["outcome"]

    org_id = ctx.payload.get("org_id", SENTINEL_ORG_ID)

    signal = PreferenceSignal(
        id=uuid4(),
        user_id=ctx.subject_id,
        org_id=org_id,
        signal_type="engagement_outcome",
        payload={
            "engagement": ctx.engagement,
            "outcome": outcome,
        },
        source="primer_core.orchestrator",
    )

    ctx.memory.ingest(
        ctx.subject_id,
        signal,
    )


async def on_struggle(ctx: HookContext) -> None:
    """Route a struggling subject to a simpler schema-defined engagement."""
    if not ctx.payload.get("struggling", False):
        return

    engagements = ctx.schema.engagements

    try:
        current_index = engagements.index(ctx.engagement)
    except ValueError:
        return

    if current_index == 0:
        return

    ctx.payload["next_skill"] = engagements[current_index - 1]
