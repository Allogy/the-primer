"""
Narrated memory write-back demo.

Runs an engagement, persists its outcome through
MemoryCore.ingest -> FileMemoryStore, then constructs a second session over
the same store and verifies that assemble_working_memory surfaces the first
session's outcome.

The reusable run_memory_roundtrip helper is consumed by the dual-domain exit
demo while run_demo preserves the original education-only entrypoint.
"""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path

from capillary_actions_sdk.models.student_model import MemoryEntry
from capillary_actions_sdk.schema.domain_schema import DomainSchema

from primer_core.adapters.capillary.file_memory_store import FileMemoryStore
from primer_core.domains import DomainPack, load_domain_pack
from primer_core.eval.cases import EngagementEvalCase
from primer_core.eval.metrics import find_eval_case
from primer_core.memory.core import MemoryCore
from primer_core.orchestrator.engagement import EngagementOrchestrator
from primer_core.orchestrator.hooks import HookEvent, HookRegistry
from primer_core.orchestrator.writeback import write_back_outcome
from primer_core.skills import SkillRegistry
from primer_core.testing.fakes import FakeRunWorkflowPort


async def run_memory_roundtrip(
    domain: str,
    case: EngagementEvalCase | None = None,
) -> bool:
    """Prove that engagement write-back survives into a second session."""
    if case is None:
        case = find_eval_case(domain)

    file_path = Path(__file__).parent / "demo_memories" / "demo_memory.json"
    file_path.parent.mkdir(parents=True, exist_ok=True)

    hooks = HookRegistry()
    hooks.register(
        event=HookEvent.AFTER_ENGAGEMENT,
        fn=write_back_outcome,
    )

    case.orchestrator.memory.store = FileMemoryStore(path=file_path)
    case.orchestrator.hooks = hooks

    output = case.orchestrator.runner.response.output

    if not isinstance(output, dict):
        print(f"[{domain}] workflow output is not a mapping --> MEMORY DEMO FAILURE")
        return False

    output["writeback"] = {
        "dimension": case.orchestrator.schema.dimension_names[0],
        "content": {},
    }

    await case.orchestrator.run_engagement(
        skill_name=case.skill_name,
        subject_id=case.subject_id,
        thread_id=case.thread_id,
        input_data=case.input_data,
    )

    pack: DomainPack = load_domain_pack(domain)
    schema: DomainSchema = pack.schema
    skills: SkillRegistry = pack.skills

    second_response = deepcopy(case.orchestrator.runner.response)

    second_memory = MemoryCore(
        schema=schema,
        store=FileMemoryStore(path=file_path),
    )

    second_orchestrator = EngagementOrchestrator(
        schema=schema,
        runner=FakeRunWorkflowPort(second_response),
        memory=second_memory,
        skills=skills,
    )

    session_1_outcome_entries: list[MemoryEntry] = await case.orchestrator.memory.store.get(
        subject_id=case.subject_id
    )

    session_2_working_memory_entries: list[MemoryEntry] = (
        await second_orchestrator.memory.assemble_working_memory(subject_id=case.subject_id)
    ).entries

    with open(file_path, "w") as temp_file:
        json.dump({}, temp_file)

    print(
        f"""
[{domain}] Session 1 outcome
MemoryCore.ingest -> FileMemoryStore(path={file_path})
---------------------------------------------------------
{session_1_outcome_entries}

[{domain}] Session 2 working memory
same FileMemoryStore path
---------------------------------------------------------
{session_2_working_memory_entries}
"""
    )

    passed = session_1_outcome_entries == session_2_working_memory_entries != []

    if passed:
        print(
            f"[{domain}] assemble_working_memory surfaces "
            "the first session's outcome --> MEMORY PASS / DEMO SUCCESS"
        )
    else:
        print(
            f"[{domain}] second-session working memory does not match "
            "the first session outcome --> MEMORY FAIL"
        )

    return passed


async def run_demo() -> int:
    passed = await run_memory_roundtrip("education")
    return 0 if passed else 1


def main() -> int:
    return asyncio.run(run_demo())


if __name__ == "__main__":
    raise SystemExit(main())
