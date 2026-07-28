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
from importlib import import_module
from pathlib import Path

from capillary_actions_sdk.schema.domain_schema import DomainSchema, load
from pydantic import BaseModel, ConfigDict

from primer_core.skills import SkillRegistry

WDF_SUFFIX = ".workflow.yaml"

# Example manifests (the SDK's education one included) list a literal '...' as a
# stand-in for "more engagements to come". It is not a real engagement and has
# no workflow definition, so it is skipped when checking pack completeness.
PLACEHOLDER_ENGAGEMENT = "..."

# Public domain keys. These are the frozen contract for load_domain_pack();
# note the hyphen in 'coop-finance' (it mirrors the manifest's `domain:` value,
# not the Python package name `coop_finance`).
EDUCATION = "education"
COOP_FINANCE = "coop-finance"


class DomainPack(BaseModel):
    """A domain's schema, skills, and knowledge base wiring, bundled together.

    Immutability is shallow. `frozen=True` blocks *field reassignment*
    (`pack.kb_names = [...]` raises) but it cannot freeze the objects the
    fields point at: `pack.kb_names.append(...)` and `pack.skills.register(...)`
    would still mutate in place. A pack is shared across every engine
    construction for its domain, so consumers must treat `kb_names` and
    `skills` as read-only — copy before modifying (`list(pack.kb_names)`) rather
    than mutating the pack's own state.
    """

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

    A pack that is missing its workflow definitions is a packaging bug, and it
    must not be papered over: `Path.glob` on a nonexistent directory returns
    empty, which would otherwise yield a valid-looking pack with zero skills
    that dies much later as a bare KeyError inside run_engagement.

    Raises:
        FileNotFoundError: if `wdf_dir` is not a directory.
        ValueError: if a declared engagement has no workflow definition.
    """
    schema = load(str(manifest_path))

    if not wdf_dir.is_dir():
        raise FileNotFoundError(
            f"no workflow definition directory for domain {schema.domain!r}: "
            f"{wdf_dir} is missing or is not a directory "
            f"(expected *{WDF_SUFFIX} documents there)"
        )

    skills = SkillRegistry()
    registered: set[str] = set()
    for wdf_path in sorted(wdf_dir.glob(f"*{WDF_SUFFIX}")):
        engagement = wdf_path.name.removesuffix(WDF_SUFFIX)
        skills.register(engagement, str(wdf_path))
        registered.add(engagement)

    missing = [
        engagement
        for engagement in schema.engagements
        if engagement != PLACEHOLDER_ENGAGEMENT and engagement not in registered
    ]
    if missing:
        raise ValueError(
            f"domain {schema.domain!r} declares engagements with no workflow "
            f"definition in {wdf_dir}: {missing} "
            f"(expected files: {[f'{name}{WDF_SUFFIX}' for name in missing]})"
        )

    return DomainPack(
        schema=schema,
        skills=skills,
        kb_names=list(schema.knowledge_base.kb_names),
    )


# Domain key -> (module path, builder attribute). The values are *strings* so
# that resolving one domain never imports another: a broken dependency inside
# one pack must not stop every other domain from loading. Registering a new
# domain is one line here plus its subpackage — still no engine edit.
_BUILDERS: dict[str, tuple[str, str]] = {
    EDUCATION: ("primer_core.domains.education", "build_education_pack"),
    COOP_FINANCE: ("primer_core.domains.coop_finance", "build_coop_finance_pack"),
}


def _builder(name: str) -> Callable[[], DomainPack]:
    """Import just the requested domain's subpackage and return its builder."""
    try:
        module_path, attribute = _BUILDERS[name]
    except KeyError:
        known = sorted(_BUILDERS)
        raise ValueError(f"unknown domain {name!r} (known: {known})") from None

    return getattr(import_module(module_path), attribute)


def load_domain_pack(name: str) -> DomainPack:
    """Load the DomainPack registered under `name`.

    Only the requested domain's subpackage is imported.

    Args:
        name: A domain key — 'education' or 'coop-finance'.

    Raises:
        ValueError: if `name` is not a known domain.
    """
    return _builder(name)()
