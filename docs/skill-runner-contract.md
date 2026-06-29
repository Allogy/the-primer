# Skill and Runner Contract

## Purpose

This document freezes the interface between Primer skill registration and
workflow execution.

The `SkillRegistry` maps stable skill names to Workflow Definition Format
documents. The `EngagementOrchestrator` resolves registered skills and delegates
their execution through the existing Capillary platform workflow ports.

## SkillRegistry interface

```python
from pathlib import Path
from uuid import UUID


class SkillRegistry:
    def register(self, name: str, path: str) -> None:
        """Register a skill name and its WDF document path."""

    def get(self, name: str) -> Path:
        """Return the WDF path registered for a skill."""

    def load_wdf(self, name: str) -> dict:
        """Load and return the registered WDF YAML document."""

    def workflow_id(self, name: str) -> UUID:
        """Return the deterministic UUID5 derived from the skill name."""
```

## Initial skill names

The canonical initial skill names are:

* `explain_concept`
* `assess_understanding`

These names use `snake_case` and must exactly match the values declared in
each domain manifest's `engagements` list.

## Skill path registration

Skill registration is path-based:

```python
skills.register("explain_concept", path)
skills.register("assess_understanding", path)
```

The exact WDF locations are supplied during registration and are not fixed by
this contract.

## Runner dependency

The `EngagementOrchestrator` reuses the existing platform ports:

* `RunWorkflowPort`
* `ResumeWorkflowPort`
* `EventStreamPort` for Week 3 streaming

`EventStreamPort` is reserved for the Week 3 streaming extension and is not
required for the Week 1 contract implementation.

No new `WorkflowRunnerPort` will be introduced.

## EngagementOrchestrator constructor

The frozen constructor is:

```python
EngagementOrchestrator(
    schema,
    runner,
    memory,
    skills,
    hooks=None,
)
```

The constructor does not accept `agent` or `triggers`.
