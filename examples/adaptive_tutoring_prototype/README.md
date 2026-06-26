# Adaptive Tutoring Prototype

This directory contains the Spring 2026 adaptive tutoring prototype done by Joseph.

The prototype demonstrates how a tutoring flow can be defined declaratively in YAML and executed as a LangGraph state machine. It is included as an experimental design reference for Primer's learning-action system.

## Files

* `routine_graph.py` — loads and executes a YAML tutoring routine
* `routine.yaml` — runnable exercise-focused tutoring flow
* `routine_v2.yaml` — expanded design artifact for a more flexible tutoring flow

`routine_v2.yaml` is not currently executable by `routine_graph.py`. It introduces additional step types and routing labels that are not yet implemented by the prototype runner.

## Features

The runnable prototype supports:

* learner profile and session-goal collection
* YAML-defined tutoring steps
* personalized tutor responses
* learner-response classification
* route labels derived from YAML
* correct, incorrect, stuck, and off-topic handling
* continuation routing using yes, no, and unclear
* configurable LangGraph recursion limits
* separate models for tutoring responses and route classification

## Installation

From the repository root, install the optional prototype dependencies:

```bash
uv sync --extra adaptive-tutoring
```

The optional dependency group includes:

* `pyyaml`
* `python-dotenv`
* `langgraph`
* `langchain-openrouter`

## Environment configuration

The prototype uses OpenRouter through `ChatOpenRouter`.

Create a local `.env` file containing:

```text
OPENROUTER_API_KEY=your_openrouter_api_key
```

Do not commit the `.env` file or API key to the repository.

## Running the prototype

From the repository root:

```bash
uv run --extra adaptive-tutoring \
  python examples/adaptive_tutoring_prototype/routine_graph.py
```

The program will ask for:

* learner name
* session goals
* difficulty level
* current level
* learning preferences
* target concepts

It will then begin an interactive terminal tutoring session.

## Routine loading

Routine paths are resolved relative to `routine_graph.py`, so the prototype can be launched from the repository root or another working directory.

## Relationship to Primer skills

The prototype's `routine.yaml` format is an experimental instructional-flow schema. It is not the production Workflow Definition Format consumed by `SkillRegistry`.

A future adapter or schema migration would be needed to translate these routine definitions into registered Primer skills and platform-executable workflows.

## Prototype scope

This example does not currently:

* implement the production `SkillRegistry`
* use `RunWorkflowPort` or `ResumeWorkflowPort`
* persist learner state to the knowledge graph
* provide AG-UI event streaming
* use LangGraph interrupt/resume for human input
* make `routine_v2.yaml` executable
* include a complete automated test suite

Terminal input is currently performed with Python's blocking `input()` function. A production implementation would use Primer's platform boundaries and LangGraph interrupt/resume behavior.

## Security note

Learner text is inserted into model prompts. This prototype does not yet include production-grade prompt-injection defenses and should not be used with untrusted input in a deployed environment.
