"""Reference handlers for writing engagement outcomes to memory."""

from uuid import UUID, uuid4

from capillary_actions_sdk.models.student_model import PreferenceSignal

from primer_core.orchestrator.hooks import HookContext

SENTINEL_ORG_ID = UUID("00000000-0000-0000-0000-000000000000")


async def write_back_outcome(ctx: HookContext) -> None:
    """Persist a schema-aligned engagement outcome to memory."""
    writeback = ctx.payload.get("writeback")
    outcome = ctx.payload.get("outcome")

    if writeback is None and isinstance(outcome, dict):
        writeback = outcome.get("writeback")

    if not isinstance(writeback, dict):
        raise ValueError("Engagement outcome must contain a writeback mapping")

    dimension = writeback.get("dimension")
    content = writeback.get("content")

    if not isinstance(dimension, str):
        raise ValueError("Writeback dimension must be a string")

    if not isinstance(content, dict):
        raise ValueError("Writeback content must be a dictionary")

    raw_org_id = ctx.payload.get("org_id", SENTINEL_ORG_ID)
    org_id = raw_org_id if isinstance(raw_org_id, UUID) else UUID(str(raw_org_id))

    signal = PreferenceSignal(
        id=uuid4(),
        user_id=ctx.subject_id,
        org_id=org_id,
        signal_type="engagement_outcome",
        payload={
            "dimension": dimension,
            "content": dict(content),
        },
        source="primer_core.orchestrator",
    )

    await ctx.memory.ingest(ctx.subject_id, signal)


async def on_struggle(ctx: HookContext) -> None:
    """Route a struggling subject to a simpler schema-defined engagement."""
    if ctx.payload.get("struggling") is not True:
        return

    engagements = ctx.schema.engagements

    try:
        current_index = engagements.index(ctx.engagement)
    except ValueError:
        return

    if current_index == 0:
        return

    ctx.payload["next_skill"] = engagements[current_index - 1]
