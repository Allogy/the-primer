"""Skill registration and Workflow Definition Format loading."""

from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import yaml


class SkillRegistry:
    """Map stable skill names to Workflow Definition Format documents."""

    def __init__(self) -> None:
        self._skills: dict[str, Path] = {}

    def register(self, name: str, path: str) -> None:
        self._skills[name] = Path(path)

    def get(self, name: str) -> Path:
        return self._skills[name]

    def load_wdf(self, name: str) -> dict:
        path = self.get(name)

        with path.open(encoding="utf-8") as file:
            document = yaml.safe_load(file)

        if not isinstance(document, dict):
            raise ValueError(f"WDF document for {name!r} must be a mapping")

        return document

    def workflow_id(self, name: str) -> UUID:
        self.get(name)
        return uuid5(NAMESPACE_URL, f"primer-core:skill:{name}")
