"""Acceptance tests for load_domain_pack (KG-W5 / RAG-1847)."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path
from uuid import uuid4

import pytest
from capillary_actions_sdk.models.student_model import MemoryEntry
from capillary_actions_sdk.schema.domain_schema import validate_memory_entry

from primer_core.domains import load_domain_pack

FINANCE_ENGAGEMENTS = ("explain-product", "suggest-allocation", "assess-readiness")


class TestEducationPack:
    def test_schema_describes_the_education_domain(self) -> None:
        pack = load_domain_pack("education")

        assert pack.schema.domain == "education"
        assert pack.schema.subject == "learner"

    def test_kb_names_come_from_the_manifest(self) -> None:
        pack = load_domain_pack("education")

        assert pack.kb_names == ["primer-education-kb"]
        assert pack.kb_names == list(pack.schema.knowledge_base.kb_names)

    def test_tutor_concept_skill_is_registered(self) -> None:
        pack = load_domain_pack("education")

        assert isinstance(pack.skills.get("tutor-concept"), Path)
        assert pack.skills.load_wdf("tutor-concept")["name"] == "tutor-concept"

    def test_the_ellipsis_placeholder_is_not_registered_as_a_skill(self) -> None:
        pack = load_domain_pack("education")

        assert "..." in pack.schema.engagements
        assert pack.workflow_definition("...") is None

    def test_workflow_definition_resolves_for_known_and_unknown_engagements(self) -> None:
        pack = load_domain_pack("education")

        definition = pack.workflow_definition("tutor-concept")

        assert definition is not None
        assert Path(definition).is_file()
        assert pack.workflow_definition("unknown") is None


class TestCoopFinancePack:
    def test_schema_describes_the_coop_finance_domain(self) -> None:
        pack = load_domain_pack("coop-finance")

        assert pack.schema.domain == "coop-finance"
        assert pack.schema.subject == "member"

    def test_dimensions_are_exactly_the_four_finance_dimensions(self) -> None:
        pack = load_domain_pack("coop-finance")

        assert pack.schema.dimension_names == [
            "financial_history",
            "risk_appetite",
            "goals",
            "habits",
        ]

    def test_kb_names_come_from_the_manifest(self) -> None:
        pack = load_domain_pack("coop-finance")

        assert pack.kb_names == ["primer-coop-finance-kb"]
        assert pack.kb_names == list(pack.schema.knowledge_base.kb_names)

    def test_manifest_declares_the_three_finance_engagements(self) -> None:
        pack = load_domain_pack("coop-finance")

        assert pack.schema.engagements == list(FINANCE_ENGAGEMENTS)

    @pytest.mark.parametrize("engagement", FINANCE_ENGAGEMENTS)
    def test_each_engagement_has_a_registered_loadable_wdf(self, engagement: str) -> None:
        pack = load_domain_pack("coop-finance")

        definition = pack.workflow_definition(engagement)

        assert definition is not None
        assert Path(definition).is_file()
        assert pack.skills.load_wdf(engagement)["name"] == engagement

    def test_memory_entries_validate_against_the_finance_dimensions(self) -> None:
        pack = load_domain_pack("coop-finance")
        entry = MemoryEntry(
            id=uuid4(),
            tier="short_term",
            dimension="risk_appetite",
            content={"tolerance": "moderate"},
        )

        validate_memory_entry(entry, pack.schema)

        rejected = MemoryEntry(
            id=uuid4(),
            tier="short_term",
            dimension="history",
            content={"courses": []},
        )
        with pytest.raises(ValueError):
            validate_memory_entry(rejected, pack.schema)


class TestLazyDomainImports:
    """Loading one domain must not import any other domain's subpackage."""

    @staticmethod
    def _imported_domains(requested: str) -> list[str]:
        """Load `requested` in a clean interpreter and report the domain modules imported."""
        script = textwrap.dedent(
            f"""
            import sys

            from primer_core.domains import load_domain_pack

            load_domain_pack({requested!r})

            prefix = "primer_core.domains."
            print(
                "\\n".join(
                    sorted(name for name in sys.modules if name.startswith(prefix))
                )
            )
            """
        )
        completed = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.split()

    def test_loading_education_does_not_import_coop_finance(self) -> None:
        imported = self._imported_domains("education")

        assert "primer_core.domains.education" in imported
        assert "primer_core.domains.coop_finance" not in imported

    def test_loading_coop_finance_does_not_import_education(self) -> None:
        imported = self._imported_domains("coop-finance")

        assert "primer_core.domains.coop_finance" in imported
        assert "primer_core.domains.education" not in imported


class TestUnknownDomain:
    def test_unknown_domain_raises_value_error_naming_the_valid_keys(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            load_domain_pack("astrology")

        message = str(excinfo.value)

        assert "astrology" in message
        assert "education" in message
        assert "coop-finance" in message

    def test_underscore_spelling_is_not_a_valid_key(self) -> None:
        with pytest.raises(ValueError):
            load_domain_pack("coop_finance")
