"""Education domain pack.

The schema comes from the SDK's example education manifest — education is the
SDK's own reference domain, so the-primer consumes it rather than re-declaring
it. The workflow definitions ship inside this package (`wdf/`) so a pack keeps
working when installed from a wheel.
"""

from __future__ import annotations

from pathlib import Path

import capillary_actions_sdk
from primer_core.domains.domain_pack import DomainPack, build_pack

WDF_DIR = Path(__file__).parent / "wdf"


def _manifest_path() -> Path:
    return (
        Path(capillary_actions_sdk.__file__).parent
        / "schema"
        / "examples"
        / "education.manifest.yaml"
    )


def build_education_pack() -> DomainPack:
    """Build the education DomainPack (subject: learner, KB: primer-education-kb)."""
    return build_pack(_manifest_path(), WDF_DIR)


__all__ = ["build_education_pack"]
