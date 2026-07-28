"""Co-operative finance domain pack.

Unlike education (whose manifest is the SDK's reference example), the
coop-finance manifest is authored here alongside its workflow definitions, so
the whole pack ships as one package directory.
"""

from __future__ import annotations

from pathlib import Path

from primer_core.domains.domain_pack import DomainPack, build_pack

MANIFEST_PATH = Path(__file__).parent / "coop-finance.manifest.yaml"
WDF_DIR = Path(__file__).parent / "wdf"


def build_coop_finance_pack() -> DomainPack:
    """Build the coop-finance DomainPack (subject: member, KB: primer-coop-finance-kb)."""
    return build_pack(MANIFEST_PATH, WDF_DIR)


__all__ = ["build_coop_finance_pack"]
