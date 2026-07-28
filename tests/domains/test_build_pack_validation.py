"""build_pack must fail loudly on packaging faults (KG-W5 / RAG-1847).

A pack with missing workflow definitions is a packaging bug. Left unchecked it
produces a valid-looking pack with zero skills that only dies much later as a
bare KeyError inside run_engagement.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from primer_core.domains.domain_pack import build_pack

MANIFEST = {
    "domain": "test-domain",
    "subject": "member",
    "dimensions": [{"name": "goals", "fields": ["targets"]}],
    "knowledge_base": {"kb_names": ["test-kb"]},
    "engagements": ["present", "absent"],
}


def _manifest(tmp_path: Path, **overrides: object) -> Path:
    path = tmp_path / "test-domain.manifest.yaml"
    path.write_text(yaml.safe_dump(MANIFEST | overrides), encoding="utf-8")
    return path


def _wdf(wdf_dir: Path, name: str) -> None:
    wdf_dir.mkdir(exist_ok=True)
    (wdf_dir / f"{name}.workflow.yaml").write_text(
        yaml.safe_dump({"name": name, "entry": "start", "exit": "end", "nodes": {}}),
        encoding="utf-8",
    )


class TestMissingWorkflowDirectory:
    def test_nonexistent_wdf_dir_raises_file_not_found(self, tmp_path: Path) -> None:
        manifest_path = _manifest(tmp_path)
        bogus = tmp_path / "no-such-wdf-dir"

        with pytest.raises(FileNotFoundError) as excinfo:
            build_pack(manifest_path, bogus)

        message = str(excinfo.value)
        assert str(bogus) in message
        assert "test-domain" in message

    def test_a_file_where_the_wdf_dir_should_be_raises_file_not_found(self, tmp_path: Path) -> None:
        manifest_path = _manifest(tmp_path)
        not_a_dir = tmp_path / "wdf"
        not_a_dir.write_text("", encoding="utf-8")

        with pytest.raises(FileNotFoundError):
            build_pack(manifest_path, not_a_dir)


class TestUnregisteredEngagements:
    def test_declared_engagement_without_a_wdf_raises_value_error(self, tmp_path: Path) -> None:
        manifest_path = _manifest(tmp_path)
        wdf_dir = tmp_path / "wdf"
        _wdf(wdf_dir, "present")

        with pytest.raises(ValueError) as excinfo:
            build_pack(manifest_path, wdf_dir)

        message = str(excinfo.value)
        assert "['absent']" in message
        assert "['absent.workflow.yaml']" in message

    def test_empty_wdf_dir_reports_every_declared_engagement(self, tmp_path: Path) -> None:
        manifest_path = _manifest(tmp_path)
        wdf_dir = tmp_path / "wdf"
        wdf_dir.mkdir()

        with pytest.raises(ValueError) as excinfo:
            build_pack(manifest_path, wdf_dir)

        message = str(excinfo.value)
        assert "present" in message
        assert "absent" in message

    def test_the_ellipsis_placeholder_is_not_treated_as_a_missing_engagement(
        self, tmp_path: Path
    ) -> None:
        manifest_path = _manifest(tmp_path, engagements=["present", "..."])
        wdf_dir = tmp_path / "wdf"
        _wdf(wdf_dir, "present")

        pack = build_pack(manifest_path, wdf_dir)

        assert pack.workflow_definition("present") is not None
        assert pack.workflow_definition("...") is None

    def test_a_complete_pack_builds(self, tmp_path: Path) -> None:
        manifest_path = _manifest(tmp_path)
        wdf_dir = tmp_path / "wdf"
        _wdf(wdf_dir, "present")
        _wdf(wdf_dir, "absent")

        pack = build_pack(manifest_path, wdf_dir)

        assert pack.schema.domain == "test-domain"
        assert pack.kb_names == ["test-kb"]
        assert pack.workflow_definition("absent") is not None
