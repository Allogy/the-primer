"""DomainPack — the portable bundle that makes the engine domain-agnostic.

A pack is everything the engine needs to serve one domain: the DomainSchema
(memory dimensions, subject, KB wiring, engagements), a SkillRegistry of the
domain's packaged Workflow Definition Format documents, and the knowledge base
names those engagements retrieve from.

Construction is identical for every domain::

    pack = load_domain_pack('coop-finance')
    memory = MemoryCore(schema=pack.schema, store=store)
    orchestrator = EngagementOrchestrator(
        schema=pack.schema, runner=runner, memory=memory, skills=pack.skills
    )

Adding a domain therefore requires no engine edit — only a new subpackage under
primer_core.domains and one line in the builder table below.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from capillary_actions_sdk.schema.domain_schema import DomainSchema, load
from pydantic import BaseModel, ConfigDict

from primer_core.skills import SkillRegistry

WDF_SUFFIX = ".workflow.yaml"

# Public domain keys. These are the frozen contract for load_domain_pack();
# note the hyphen in 'coop-finance' (it mirrors the manifest's `domain:` value,
# not the Python package name `coop_finance`).
EDUCATION = "education"
COOP_FINANCE = "coop-finance"


class DomainPack(BaseModel):
    """A domain's schema, skills, and knowledge base wiring, bundled together."""

    # `schema` shadows the deprecated BaseModel.schema classmethod on purpose:
    # it is the frozen contract name, matching HookContext.schema.
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    schema: DomainSchema
    skills: SkillRegistry
    kb_names: list[str]

    def workflow_definition(self, engagement: str) -> str | None:
        """Return the WDF path for a registered engagement, or None if unknown."""
        try:
            return str(self.skills.get(engagement))
        except KeyError:
            return None


def build_pack(manifest_path: Path, wdf_dir: Path) -> DomainPack:
    """Build a pack from a manifest and a directory of `*.workflow.yaml` documents.

    Skills are discovered by globbing `wdf_dir` rather than by iterating
    `schema.engagements`, because example manifests may carry a '...'
    placeholder engagement that has no workflow definition.
    """
    schema = load(str(manifest_path))

    skills = SkillRegistry()
    for wdf_path in sorted(wdf_dir.glob(f"*{WDF_SUFFIX}")):
        skills.register(wdf_path.name.removesuffix(WDF_SUFFIX), str(wdf_path))

    return DomainPack(
        schema=schema,
        skills=skills,
        kb_names=list(schema.knowledge_base.kb_names),
    )


def _builders() -> dict[str, Callable[[], DomainPack]]:
    """Resolve the builder table lazily so domain subpackages stay unimported."""
    from primer_core.domains.coop_finance import build_coop_finance_pack
    from primer_core.domains.education import build_education_pack

    return {
        EDUCATION: build_education_pack,
        COOP_FINANCE: build_coop_finance_pack,
    }


def load_domain_pack(name: str) -> DomainPack:
    """Load the DomainPack registered under `name`.

    Args:
        name: A domain key — 'education' or 'coop-finance'.

    Raises:
        ValueError: if `name` is not a known domain.
    """
    builders = _builders()

    try:
        build = builders[name]
    except KeyError:
        known = sorted(builders)
        raise ValueError(f"unknown domain {name!r} (known: {known})") from None

    return build()
