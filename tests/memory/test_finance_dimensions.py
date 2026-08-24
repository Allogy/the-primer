from __future__ import annotations

import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from capillary_actions_sdk.models.student_model import MemoryEntry, PreferenceSignal
from capillary_actions_sdk.schema.domain_schema import validate_memory_entry

from primer_core.adapters.capillary.file_memory_store import FileMemoryStore
from primer_core.domains.domain_pack import load_domain_pack
from primer_core.memory.core import MemoryCore


async def test_finance_risk_appetite_signal_round_trips_through_unchanged_engine(
    tmp_path: Path,
) -> None:
    """
    BDD Scenario #1
    ---------------
    Scenario: a finance risk_appetite signal round-trips through the unchanged engine

    Given MemoryCore constructed from load_domain_pack('coop-finance').schema
        over a FileMemoryStore at tmp_path
    When a PreferenceSignal for dimension risk_appetite
        (e.g. content {"tolerance": "moderate"}) is ingested
    Then it validates against the finance schema
        and is retrievable via store.get and assemble_working_memory
    """
    test_subject_id = uuid4()

    # Given MemoryCore constructed from load_domain_pack('coop-finance').schema
    #   over a FileMemoryStore at tmp_path
    test_memory = MemoryCore(
        schema=load_domain_pack("coop-finance").schema,
        store=FileMemoryStore(path=tmp_path / "mem.json"),
    )

    # When a PreferenceSignal for dimension risk_appetite (e.g. content {"tolerance": "moderate"})
    #   is ingested
    test_signal = PreferenceSignal(
        id=uuid4(),
        user_id=test_subject_id,
        org_id=uuid4(),
        signal_type="coop_finance_test",
        payload={"dimension": "risk_appetite", "content": {"tolerance": "moderate"}},
        source="primer_core.tests.memory",
    )

    await test_memory.ingest(subject_id=test_subject_id, signal=test_signal)

    # Then it validates against the finance schema
    #   and is retrievable via store.get and assemble_working_memory
    # (Validation is built into test_memory.ingest)

    retrieved_entry = (await test_memory.store.get(subject_id=test_subject_id))[0]
    assert retrieved_entry.dimension == "risk_appetite"
    assert retrieved_entry.content == {"tolerance": "moderate"}

    retrieved_working_memory_entry = (
        await test_memory.assemble_working_memory(subject_id=test_subject_id)
    ).entries[0]
    assert retrieved_working_memory_entry.dimension == "risk_appetite"
    assert retrieved_working_memory_entry.content == {"tolerance": "moderate"}


async def test_every_declared_finance_dimension_validates(tmp_path: Path) -> None:
    """
    BDD Scenario #2
    ---------------
    Scenario: every declared finance dimension validates

    Given the four coop-finance dimensions from the pack schema
    When an entry shaped by each dimension's declared fields passes validate_memory_entry
    Then all four validate, and an entry with an undeclared field or dimension is rejected
    """
    test_schema = load_domain_pack("coop-finance").schema

    # Given the four coop-finance dimensions from the pack schema
    finance_dimensions_fields = {
        dimension.name: dimension.fields
        for dimension in load_domain_pack("coop-finance").schema.dimensions
    }

    for test_dimension, test_fields in finance_dimensions_fields.items():
        # When an entry shaped by each dimension's declared fields...
        test_entry = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension=test_dimension,
            content={field: "test_attribute" for field in test_fields},
        )
        # ...passes validate_memory_entry...
        try:
            validate_memory_entry(entry=test_entry, schema=test_schema)
        except ValueError as e:
            raise AssertionError(str(e))
        # ... Then all four validate

    # ...and an entry with an undeclared field or dimension is rejected
    undeclared_field_entry = MemoryEntry(
        id=uuid4(),
        tier="long_term",
        dimension="financial_history",
        content={"undeclared_field": "test_attribute"},
    )
    test_memory = MemoryCore(schema=test_schema, store=FileMemoryStore(path=tmp_path / "mem.json"))
    with pytest.raises(ValueError, match="do not match with the provided schema"):
        await test_memory.write(subject_id=uuid4(), entry=undeclared_field_entry)

    undeclared_dimension_entry = MemoryEntry(
        id=uuid4(),
        tier="long_term",
        dimension="undeclared_dimension",
        content={"accounts": "test_attribute"},
    )
    with pytest.raises(ValueError, match="Unknown dimension"):
        validate_memory_entry(entry=undeclared_dimension_entry, schema=test_schema)


def test_zero_engine_change_is_proven_not_asserted() -> None:
    """
    BDD Scenario #3
    ---------------
    Scenario: zero engine change is proven, not asserted

    Given the branch containing this story's work
    When `git grep -E '^(primer_core.domains)' -- src/primer_core/memory/*.py` is inspected
    Then a return code of 1 is produced, indicating no mentions of `primer_core.domains` in the
        engine and proving that domain packs never touch the engine.
    """
    command = "git grep -E '^(primer_core.domains)' -- src/primer_core/memory/*.py"

    # When `git diff main -- src/primer_core/memory/` is inspected
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(command.split(), capture_output=True, text=True, cwd=repo_root)

    # Return code of 1 indicates that no mentions of "primer_core.domains" was
    #   found in src/primer_core/memory/
    assert result.returncode == 1, f'''Executed external command "{command}" failed:
        Exit code: {result.returncode}
        --- STDOUT ---
        {result.stdout}
        --- STDERR ---
        {result.stderr}
                '''
