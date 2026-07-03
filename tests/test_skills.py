"""Tests for primer_cores.skills.SkillRegistry."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
import yaml

from primer_core.skills import SkillRegistry


@pytest.fixture
def tutor_wdf(tmp_path: Path) -> Path:
    """Create a minimal valid tutor-concept WDF for registry tests."""
    path = tmp_path / "tutor-concept.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "name": "tutor-concept",
                "entry": "explain",
                "exit": "complete",
                "nodes": {
                    "explain": {
                        "type": "instruction",
                    },
                    "complete": {
                        "type": "terminal",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


class TestSkillRegistry:
    def test_real_tutor_concept_is_valid(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        wdf_path = repository_root / "src" / "primer_core" / "wdfs" / "tutor-concept.yaml"

        assert wdf_path.is_file()

        registry = SkillRegistry()
        registry.register("tutor-concept", str(wdf_path))

        document = registry.load_wdf("tutor-concept")

        assert {"name", "entry", "exit", "nodes"} <= document.keys()
        assert document["name"] == "tutor-concept"
        assert isinstance(document["nodes"], dict)
        assert document["entry"] in document["nodes"]
        assert document["exit"] in document["nodes"]

    def test_register_and_get_returns_wdf_path(self, tutor_wdf: Path) -> None:
        registry = SkillRegistry()

        registry.register("tutor-concept", str(tutor_wdf))

        result = registry.get("tutor-concept")

        assert result == tutor_wdf
        assert isinstance(result, Path)

    def test_get_unknown_skill_raises_key_error(self) -> None:
        registry = SkillRegistry()

        with pytest.raises(KeyError):
            registry.get("unknown-skill")

    def test_load_wdf_parses_yaml_document(self, tutor_wdf: Path) -> None:
        registry = SkillRegistry()
        registry.register("tutor-concept", str(tutor_wdf))

        document = registry.load_wdf("tutor-concept")

        assert document["name"] == "tutor-concept"
        assert document["entry"] == "explain"
        assert document["exit"] == "complete"
        assert set(document["nodes"]) == {"explain", "complete"}

    def test_load_wdf_unknown_skill_raises_key_error(self) -> None:
        registry = SkillRegistry()

        with pytest.raises(KeyError):
            registry.load_wdf("unknown-skill")

    def test_workflow_id_is_stable_uuid5(self, tutor_wdf: Path) -> None:
        registry = SkillRegistry()
        registry.register("tutor-concept", str(tutor_wdf))

        first = registry.workflow_id("tutor-concept")
        second = registry.workflow_id("tutor-concept")

        assert first == second
        assert isinstance(first, UUID)
        assert first.version == 5

    def test_different_skill_names_produce_different_ids(
        self,
        tutor_wdf: Path,
    ) -> None:
        registry = SkillRegistry()
        registry.register("tutor-concept", str(tutor_wdf))
        registry.register("assess-understanding", str(tutor_wdf))

        tutor_id = registry.workflow_id("tutor-concept")
        assessment_id = registry.workflow_id("assess-understanding")

        assert tutor_id != assessment_id

    def test_workflow_id_unknown_skill_raises_key_error(self) -> None:
        registry = SkillRegistry()

        with pytest.raises(KeyError):
            registry.workflow_id("unknown-skill")
