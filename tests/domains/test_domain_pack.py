"""Shape tests for the DomainPack model itself (KG-W5 / RAG-1847)."""

from __future__ import annotations

import pytest
from capillary_actions_sdk.schema.domain_schema import DomainSchema
from pydantic import ValidationError

from primer_core.domains import DomainPack, load_domain_pack
from primer_core.skills import SkillRegistry


@pytest.fixture
def education_pack() -> DomainPack:
    return load_domain_pack("education")


@pytest.fixture
def finance_pack() -> DomainPack:
    return load_domain_pack("coop-finance")


class TestDomainPackShape:
    def test_both_domains_produce_the_same_pack_type(
        self,
        education_pack: DomainPack,
        finance_pack: DomainPack,
    ) -> None:
        assert type(education_pack) is DomainPack
        assert type(finance_pack) is DomainPack

    def test_pack_fields_have_the_contract_types(self, education_pack: DomainPack) -> None:
        assert isinstance(education_pack.schema, DomainSchema)
        assert isinstance(education_pack.skills, SkillRegistry)
        assert isinstance(education_pack.kb_names, list)
        assert all(isinstance(name, str) for name in education_pack.kb_names)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("kb_names", ["other-kb"]),
            ("skills", SkillRegistry()),
        ],
    )
    def test_pack_fields_cannot_be_reassigned(
        self,
        education_pack: DomainPack,
        field: str,
        value: object,
    ) -> None:
        """frozen=True blocks reassignment. It does NOT deep-freeze the field values.

        `kb_names.append(...)` and `skills.register(...)` still mutate in place —
        see the DomainPack docstring; consumers must treat them as read-only.
        """
        with pytest.raises(ValidationError):
            setattr(education_pack, field, value)

        assert education_pack.kb_names == ["primer-education-kb"]

    def test_workflow_definition_returns_a_path_string_for_a_known_engagement(
        self,
        education_pack: DomainPack,
    ) -> None:
        definition = education_pack.workflow_definition("tutor-concept")

        assert isinstance(definition, str)
        assert definition.endswith("tutor-concept.workflow.yaml")

    def test_workflow_definition_returns_none_for_an_unknown_engagement(
        self,
        education_pack: DomainPack,
    ) -> None:
        assert education_pack.workflow_definition("no-such-engagement") is None
