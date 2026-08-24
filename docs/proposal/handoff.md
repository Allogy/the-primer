# Primer Core Production Handoff

This document summarizes the Primer Core prototype at program exit and maps the current reference implementations to the services a production deployment would need.

The prototype demonstrates that the same orchestration, memory, retrieval, and streaming contracts can support both the `education` and `coop-finance` DomainPacks through shared Primer Core interfaces.

The program-exit demonstration combines the three workstreams:

* Knowledge Graph: domain-pack retrieval wiring and domain-swap parity.
* Learning Data: schema-validated memory persistence and store conformance.
* Didactic Skills: declarative engagements, lifecycle hooks, AG-UI streaming, write-back, and failure handling.

## Production Adapter Mapping

Primer Core is organized around ports so that test and reference implementations can be replaced without changing the orchestration layer.

### Workflow Execution

Prototype and evaluation code commonly uses:

`FakeRunWorkflowPort`

The existing Capillary adapter is:

`WorkflowCliRunner`

`WorkflowCliRunner` implements `RunWorkflowPort` and `ResumeWorkflowPort` and provides the current bridge from Primer Core to Capillary workflow execution.

For production, the workflow adapter should continue to satisfy these port contracts regardless of whether execution remains CLI-backed or moves to a long-running service or API transport.

The orchestration layer should continue depending on the port rather than on the transport implementation.

### Knowledge Retrieval

Prototype and deterministic evaluation paths use:

`FakeKnowledgeBase`

The current retrieval adapter is:

`PgVectorKnowledgeBase`

`PgVectorKnowledgeBase` implements `KnowledgeBasePort` and delegates vector search through the `PgVectorSearchClient` protocol.

A production deployment should supply a configured pgvector-backed search client or another retrieval implementation satisfying `KnowledgeBasePort`.

Domain-specific knowledge-base selection must continue to come from the DomainPack's `KnowledgeBaseWiring` rather than from branches in the interaction agent.

### Memory Persistence

Evaluation commonly uses an in-memory store for deterministic construction and testing.

The shipped file-backed adapter is:

`FileMemoryStore`

`FileMemoryStore` implements `MemoryStorePort` and demonstrates that `MemoryCore` can persist learner or member state through a replaceable storage implementation.

A production deployment should replace the reference storage implementation with a durable `MemoryStorePort` implementation appropriate for concurrent, multi-process service operation.

The shared Learning Data conformance suite established in LD-W7 should be treated as the implementation checklist for any replacement store. A production store should preserve the same observable behavior for writes, reads, schema validation, and working-memory assembly.

## Runtime Contracts

The following contracts should be treated as stable boundaries when replacing reference adapters with production services.

### Engagement API

The public engagement contract is:

```text
run_engagement(skill_name, subject_id, thread_id, input_data=None)
```

Domain-specific behavior remains defined through DomainPacks, schemas, registered skills, and WDF YAML rather than through branches in `EngagementOrchestrator`.

### Streaming and AG-UI

`run_engagement_streaming` exposes workflow execution through typed `AGUIEvent` instances.

The streaming surface may also forward events through an `EventStreamPort`, but transport adapters must preserve the AG-UI event contract.

Structured workflow outcomes and streaming event traces are deliberately separate:

```text
payload["outcome"]         -> structured workflow output
payload["streamed_events"] -> observed AG-UI protocol events
```

A production streaming adapter should not reinterpret AG-UI events as structured workflow outcomes.

### Streaming Write-Back

Streaming cleanup executes through a `try/finally` lifecycle boundary so `AFTER_ENGAGEMENT` runs when:

* the stream completes normally;
* the consumer closes the stream early; or
* the workflow runner raises during iteration.

The original runner exception continues to propagate after cleanup.

`write_back_outcome` treats a streaming engagement with no structured write-back as a valid no-op. Explicit malformed write-back data remains an error.

Production implementations should preserve this distinction rather than constructing artificial workflow outcomes from an event stream.

### Hook Failure Policy

Hook handlers use an isolate-and-log policy.

Handlers execute sequentially in registration order. If one handler raises, the exception is logged and subsequent handlers continue executing.

Production hook implementations should preserve deterministic ordering and should not introduce concurrency that changes lifecycle ordering without an explicit contract change.

### Knowledge-Base Failure Policy

Retrieval distinguishes between two cases:

1. retrieval succeeds and returns no relevant evidence;
2. retrieval cannot run because the knowledge service is unavailable.

A typed `KnowledgeBaseUnavailable` error represents the second case.

`InteractionAgent` logs that failure and continues as a no-context interaction. Learner working memory remains available and the interaction model can still produce a response.

Unexpected retrieval exceptions continue to propagate.

Production knowledge adapters should translate known service-availability failures into `KnowledgeBaseUnavailable` rather than exposing transport-specific exceptions to the interaction layer.

### Memory Store Conformance

`MemoryCore` owns schema validation and working-memory assembly while storage is accessed through `MemoryStorePort`.

Any production replacement for the current memory adapters should be run against the shared Learning Data conformance suite before adoption.

The store implementation should preserve observable behavior across:

* persistence and retrieval;
* domain-schema dimensions;
* working-memory assembly;
* replacement of one conforming store by another; and
* cross-session visibility of persisted outcomes.

## Evaluation and Domain-Swap Guarantees

The transition evaluation suite provides executable checks for the architecture described by the proposal documents.

The current suite covers:

* `declarative_orchestration`
* `typed_models`
* `port_conformance`
* `protocol_compliance`
* `stateless_agents`
* `run_swap_parity`

`declarative_orchestration` verifies that the evaluated engagements resolve to WDF definitions through their DomainPacks.

`typed_models` checks memory dimensions against each domain schema.

`port_conformance` compares observable working-memory behavior across conforming memory-store implementations.

`protocol_compliance` verifies that the streaming surface emits only typed `AGUIEvent` instances.

`stateless_agents` checks that persistence flows through ports rather than being retained as in-process orchestrator state.

`run_swap_parity` executes the same orchestrator flow for `education` and `coop-finance` while tracing the Primer Core engine modules used by each run.

At program exit, both domains execute the same traced engine module set. This provides executable evidence that the evaluated domain swap uses the same engine path while domain-specific configuration remains supplied through the DomainPacks.

## Known Risks and Follow-On Work

### Production Storage

`FileMemoryStore` is a reference persistence adapter and should not be assumed to provide the concurrency, transaction, durability, or deployment semantics required by a production service.

A production `MemoryStorePort` implementation should be validated with the shared Learning Data conformance suite before replacement.

### External Service Availability

Workflow execution and knowledge retrieval will depend on external services in production.

The knowledge path has an explicit typed degradation policy through `KnowledgeBaseUnavailable`.

Equivalent operational policies should be defined for production workflow and event-stream transports where appropriate.

### Write-Back Delivery Semantics

The current orchestration lifecycle guarantees that the after-engagement hook is invoked during streaming cleanup, but production persistence adapters must still define their own durability and retry guarantees.

A future production specification should state whether write-back delivery is at-most-once, at-least-once, or otherwise idempotent across process failures and retries.

### Adapter Observability

Reference implementations primarily prove behavior through tests and deterministic demos.

Production adapters should expose appropriate logging, tracing, and service-health information without changing the port-level behavior expected by Primer Core.

### Domain and WDF Evolution

The architecture depends on schemas and WDF definitions remaining the authoritative description of domain behavior.

Future changes to DomainPacks, WDF validation, or the supported workflow node vocabulary should retain executable validation so malformed declarative configuration can be detected before production execution where possible.

## Running the System

Run commands from the repository root.

### Full Test Suite

```bash
uv run pytest -m 'not manual' -q
```

### Ruff

```bash
uv run ruff check .
uv run ruff format --check .
```

### Primer Evaluation Suite

```bash
uv run primer-eval
```

The console suite evaluates both:

```text
education
coop-finance
```

and reports the transition metrics plus the domain-swap parity result.

### Eval-Marked Tests

The repository defines the pytest marker:

```text
eval
```

Run the explicitly marked evaluation tests with:

```bash
uv run pytest -m eval -v
```

### Knowledge-Base Domain Swap Demo

```bash
uv run python demos/kb_domain_swap.py
```

This demo loads both DomainPacks through one shared retrieval path and reports:

* retrieval wiring;
* engine module parity; and
* zero-engine-branching status.

### Education Memory Demo

```bash
uv run python demos/demo_education.py
```

This demo:

1. runs an education engagement;
2. writes the engagement outcome through `MemoryCore.ingest`;
3. persists it through `FileMemoryStore`;
4. constructs a second session over the same store; and
5. verifies that `assemble_working_memory` surfaces the first session's persisted outcome.

### Dual-Domain Program Exit Demo

```bash
uv run python demos/demo_dual_domain.py
```

This is the combined program-exit demonstration.

For both `education` and `coop-finance`, it:

1. constructs the domain through the existing eval-case and DomainPack path;
2. runs the shared `EngagementOrchestrator` streaming surface;
3. verifies that the stream contains typed AG-UI events;
4. demonstrates memory write-back and cross-session persistence;
5. runs the existing swap-parity and transition-metric harness; and
6. runs the eval pytest suite in a bounded subprocess.

The demo exits with status `0` only when every domain leg, evaluation check, and subprocess gate passes.

## Proposal Document Set

The program-exit proposal is organized under `docs/proposal/`:

* `knowledge-graph.md` — Knowledge Graph architecture and domain wiring.
* `knowledge-graph-metrics.md` — Knowledge Graph evaluation and metrics.
* `learning-data.md` — Learning Data, memory contracts, and storage behavior.
* `didactic-skills.md` — engagement orchestration, hooks, streaming, write-back, and failure policies.
* `handoff.md` — production mapping, runtime contracts, risks, and execution instructions.

Together these documents describe the three Primer Core workstreams and the contracts required to replace prototype components with production implementations.

## Program Exit Checklist

Before handoff or merge, verify:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -m 'not manual' -q
uv run primer-eval
uv run pytest -m eval -v
uv run python demos/kb_domain_swap.py
uv run python demos/demo_education.py
uv run python demos/demo_dual_domain.py
git diff --check
```

Program exit is complete when the full suite, evaluation suite, domain-swap demo, education memory demo, and dual-domain exit demo all pass.
