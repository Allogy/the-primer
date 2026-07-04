"""Adapters that implement primer_core engine ports against Capillary infrastructure.

Owners:
  PgVectorKnowledgeBase — KG-W3 (Rianna)
  FileMemoryStore       - LD-W3 (Malakhi)
  (DS-W3 and LD-W3 add their adapters here too — coordinate like KG-W2/DS-W2 did on fakes.py)
"""

from __future__ import annotations

from primer_core.adapters.capillary.file_memory_store import FileMemoryStore
from primer_core.adapters.capillary.kb_pgvector import PgVectorKnowledgeBase

__all__ = ["FileMemoryStore", "PgVectorKnowledgeBase"]
