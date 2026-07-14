import json
from pathlib import Path
from uuid import UUID

from capillary_actions_sdk.models.student_model import MemoryEntry
from capillary_actions_sdk.ports.memory import MemoryStorePort


class FileMemoryStore(MemoryStorePort):
    def __init__(self, path: str | Path):
        self.path = path

        try:
            with open(self.path, "r", encoding="utf-8") as json_file:
                self._store = json.load(json_file)
        except (FileNotFoundError, json.JSONDecodeError):
            self._store = dict()
            with open(self.path, "w") as json_file:
                json.dump(self._store, json_file)

    async def store(self, subject_id: UUID, entry: MemoryEntry) -> None:
        if str(subject_id) in self._store.keys():
            self._store[str(subject_id)].append(entry.model_dump_json())
        else:
            self._store[str(subject_id)] = [entry.model_dump_json()]

        with open(self.path, "w") as json_file:
            json.dump(self._store, json_file)

    async def get(
        self, subject_id: UUID, dimension: str | None = None, tier: str | None = None
    ) -> list[MemoryEntry]:
        if str(subject_id) not in self._store.keys():
            return []

        entries = []
        all_entries = list(map(MemoryEntry.model_validate_json, self._store[str(subject_id)]))

        for memory in all_entries:
            if dimension in (None, memory.dimension) and tier in (None, memory.tier):
                entries.append(memory)

        return entries
