from __future__ import annotations

from uuid import uuid4

from capillary_actions_sdk.models.student_model import MemoryEntry
from capillary_actions_sdk.ports.memory import MemoryStorePort

from primer_core.adapters.capillary.file_memory_store import FileMemoryStore


class TestFileMemoryStoreInstance:
    async def test_FileMemoryStore_is_real_MemoryStorePort(self, tmp_path):
        """
        BDD Scenario #1
        ---------------
        Scenario: FileMemoryStore is a real MemoryStorePort

        Given a FileMemoryStore(path=tmp_path / 'mem.json')
        Then it is an instance of capillary_actions_sdk.ports.memory.MemoryStorePort
        """
        test_file_memory_store = FileMemoryStore(path=tmp_path / "mem.json")

        assert test_file_memory_store.__class__.__bases__[0] == MemoryStorePort


class TestFileMemoryStoreGet:
    async def test_store_then_get_returns_all_entries_for_subject(self, tmp_path):
        """
        BDD Scenario #2
        ---------------
        Scenario: store then get returns all entries for the subject

        Given entries stored in dimensions "history" and "affinities" for one subject
        When I call get(subject_id)
        Then both entries are returned
        """
        test_history_entry = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension="history",
            content={
                "courses_completed": ["APUSH", "calc-1"],
            },
        )
        test_affinities_entry = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension="affinities",
            content={
                "courses_enjoyed": ["calc-1"],
            },
        )

        test_subject_id = uuid4()

        test_file_memory_store = FileMemoryStore(path=tmp_path / "mem.json")

        await test_file_memory_store.store(subject_id=test_subject_id, entry=test_history_entry)
        await test_file_memory_store.store(subject_id=test_subject_id, entry=test_affinities_entry)

        returned_entries = await test_file_memory_store.get(subject_id=test_subject_id)

        assert test_history_entry in returned_entries
        assert test_affinities_entry in returned_entries

    async def test_get_filters_by_dimension(self, tmp_path):
        """
        BDD Scenario #3
        ---------------
        Scenario: get filters by dimension

        When I call get(subject_id, dimension='history')
        Then only the "history" entry is returned
        """
        test_history_entry = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension="history",
            content={
                "courses_completed": ["APUSH", "calc-1"],
            },
        )
        test_affinities_entry = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension="affinities",
            content={
                "courses_enjoyed": ["calc-1"],
            },
        )

        test_subject_id = uuid4()

        test_file_memory_store = FileMemoryStore(path=tmp_path / "mem.json")

        await test_file_memory_store.store(subject_id=test_subject_id, entry=test_history_entry)
        await test_file_memory_store.store(subject_id=test_subject_id, entry=test_affinities_entry)

        returned_entries = await test_file_memory_store.get(
            subject_id=test_subject_id, dimension="history"
        )

        assert test_history_entry in returned_entries
        assert test_affinities_entry not in returned_entries

    async def test_get_filters_by_tier(self, tmp_path):
        """
        BDD Scenario #4
        ---------------
        Scenario: get filters by tier

        Given entries with tiers "short_term" and "long_term"
        When I call get(subject_id, tier='short_term')
        Then only the short_term entry is returned
        """
        test_long_term_entry = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension="history",
            content={
                "courses_completed": ["APUSH", "calc-1"],
            },
        )
        test_short_term_entry = MemoryEntry(
            id=uuid4(),
            tier="short_term",
            dimension="affinities",
            content={
                "courses_enjoyed": ["calc-1"],
            },
        )

        test_subject_id = uuid4()

        test_file_memory_store = FileMemoryStore(path=tmp_path / "mem.json")

        await test_file_memory_store.store(subject_id=test_subject_id, entry=test_long_term_entry)
        await test_file_memory_store.store(subject_id=test_subject_id, entry=test_short_term_entry)

        returned_entries = await test_file_memory_store.get(
            subject_id=test_subject_id, tier="short_term"
        )

        assert test_short_term_entry in returned_entries
        assert test_long_term_entry not in returned_entries

    async def test_unknown_subject_returns_empty_list(self, tmp_path):
        """
        BDD Scenario #5
        ---------------
        Scenario: unknown subject returns an empty list
        When I call get(uuid4()) on an empty store
        Then the result is []
        """
        test_file_memory_store = FileMemoryStore(path=tmp_path / "mem.json")

        assert await test_file_memory_store.get(subject_id=uuid4()) == []

    async def test_memory_persists_across_instances(self, tmp_path):
        """
        BDD Scenario #6
        ---------------
        Scenario: memory persists across instances (process-restart property)

        Given a FileMemoryStore that stored an entry at path P
        When a NEW FileMemoryStore is constructed over the same path P
        Then get(subject_id) returns the stored entry
        """
        test_file_memory_store_1 = FileMemoryStore(path=tmp_path / "mem.json")
        test_subject_id = uuid4()
        test_entry = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension="history",
            content={
                "courses_completed": ["APUSH", "calc-1"],
            },
        )
        await test_file_memory_store_1.store(subject_id=test_subject_id, entry=test_entry)

        test_file_memory_store_2 = FileMemoryStore(path=tmp_path / "mem.json")

        result_entry_list = await test_file_memory_store_2.get(subject_id=test_subject_id)
        result_entry = result_entry_list[0]

        # Four different assertions instead of "result_entry == test_entry"
        #   because the entry's location in memory may be different
        #   after being turned into a JSON object and back
        assert result_entry.id == test_entry.id
        assert result_entry.tier == test_entry.tier
        assert result_entry.dimension == test_entry.dimension
        assert result_entry.content == test_entry.content

    async def test_round_trip_preserves_all_MemoryEntry_fields(self, tmp_path):
        """
        BDD Scenario #7
        ---------------
        Scenario: round trip preserves all MemoryEntry fields

        Given an entry with content, relevance_score=0.75, and metadata={'source': 'tutor'}
        When it is stored and read back by a fresh instance
        Then id, content, relevance_score, and metadata are identical
        """
        test_file_memory_store_1 = FileMemoryStore(path=tmp_path / "mem.json")
        test_subject_id = uuid4()
        test_entry = MemoryEntry(
            id=uuid4(),
            tier="long_term",
            dimension="history",
            content={
                "courses_completed": ["APUSH", "calc-1"],
            },
            relevance_score=0.75,
            metadata={"source": "tutor"},
        )
        await test_file_memory_store_1.store(subject_id=test_subject_id, entry=test_entry)

        test_file_memory_store_2 = FileMemoryStore(path=tmp_path / "mem.json")

        result_entry_list = await test_file_memory_store_2.get(subject_id=test_subject_id)
        result_entry = result_entry_list[0]

        assert result_entry.id == test_entry.id
        assert result_entry.content == test_entry.content
        assert result_entry.relevance_score == test_entry.relevance_score
        assert result_entry.metadata == test_entry.metadata
