"""Smoke tests for primer_core and its required dependencies."""

from __future__ import annotations


def test_primer_core_imports() -> None:
    import primer_core

    assert primer_core is not None


def test_sdk_domain_schema_imports() -> None:
    from capillary_actions_sdk.schema import DomainSchema

    assert DomainSchema is not None


def test_pydantic_ai_imports() -> None:
    from pydantic_ai import Agent
    from pydantic_ai.models.test import TestModel

    assert Agent is not None
    assert TestModel is not None
