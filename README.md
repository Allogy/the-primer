# Primer SDK

Extension SDK for the Capillary Actions platform. Provides port interfaces, data models, and AG-UI event types for building adapters and services that integrate with the platform's hexagonal architecture.

**Status:** Development (0.1.0)

**Requires:** Python >= 3.13, Pydantic >= 2.0

## Architecture

The platform uses a hexagonal (ports and adapters) architecture. This SDK exposes the port contracts and data models needed to build adapters without access to the platform internals.

```
primer_sdk/
├── events.py              # AG-UI protocol event types (universal interface)
├── ports/
│   ├── platform.py        # Platform-provided ports (RunWorkflow, EventStream, etc.)
│   ├── student_model.py   # Cohort-based preference engine ports
│   ├── cycle_loop.py      # Triggers, orchestration, agent loop ports
│   └── presentation.py    # Multi-channel adapter ports
├── models/
│   ├── student_model.py   # PreferenceSignal, Cohort, CohortSnapshot
│   ├── cycle_loop.py      # TriggerDefinition, OrchestrationPlan, AgentLoopDefinition
│   └── presentation.py    # ChannelSession, ChannelMessage, HitlGateConfig
└── reference/
    └── slack_adapter.py   # Reference ChannelAdapterPort implementation
```

### Port types

**Platform ports** (`ports/platform.py`) — ABCs representing existing platform capabilities. These are already implemented by the platform; your code invokes them.

**Extension ports** (`ports/student_model.py`, `ports/cycle_loop.py`, `ports/presentation.py`) — ABCs you implement. Each defines an inbound side (usecases the system exposes) and an outbound side (adapters you provide).

### AG-UI events

All communication between the platform and external adapters flows through the AG-UI event protocol. The `events.py` module defines the 12 base event types:

| Category | Events |
|---|---|
| Lifecycle | `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR` |
| Messages | `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END` |
| State | `STATE_SNAPSHOT`, `STATE_DELTA` |
| Tools | `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END`, `TOOL_CALL_RESULT` |

## Getting Started

### 1. Install

```bash
# Clone and install in development mode
git clone git@bitbucket.org:allogy/primer-sdk.git
cd primer-sdk
uv venv && uv sync --all-groups
```

Or install directly:

```bash
uv pip install git+ssh://git@bitbucket.org/allogy/primer-sdk.git
```

### 2. Verify installation

```bash
uv run python -c "
from primer_sdk.events import AGUIEvent, AGUIEventType
from primer_sdk.ports import ChannelAdapterPort, CohortStrategyPort
from primer_sdk.models import PreferenceSignal, TriggerDefinition, ChannelSession
print(f'primer_sdk loaded — {len(AGUIEventType)} event types')
"
```

### 3. Run tests

```bash
uv run pytest tests/ -v
```

### 4. Implement a port

Every extension starts by subclassing a port ABC. Here are three examples — one per extension domain.

**Channel adapter** (presentation layer):

```python
from primer_sdk.events import AGUIEvent, AGUIEventType
from primer_sdk.models.presentation import (
    ChannelFile,
    ChannelMessage,
    ChannelSession,
    HitlGateConfig,
)
from primer_sdk.ports.presentation import ChannelAdapterPort


class TelegramAdapter(ChannelAdapterPort):
    @property
    def channel_type(self) -> str:
        return 'telegram'

    async def send_event(self, event: AGUIEvent, session: ChannelSession) -> None:
        if event.event_type == AGUIEventType.TEXT_MESSAGE_END:
            # Buffer tokens during TEXT_MESSAGE_CONTENT, send on END
            await self._send_telegram_message(session, self._flush_buffer(session))

    async def send_error(self, error: str, session: ChannelSession) -> None:
        await self._send_telegram_message(session, f'Error: {error}')

    async def render_hitl_gate(
        self, gate_type: str, gate_config: HitlGateConfig, session: ChannelSession
    ) -> None:
        # Render as Telegram inline keyboard
        ...

    async def receive_message(self, raw_payload: dict) -> ChannelMessage:
        # Parse Telegram update object
        ...

    async def receive_file(self, raw_payload: dict) -> ChannelFile | None:
        ...

    async def resolve_session(self, raw_payload: dict) -> ChannelSession:
        ...

    async def register_webhook(self, callback_url: str) -> None:
        # Call Telegram setWebhook API
        ...

    async def health_check(self) -> bool:
        ...
```

**Cohort strategy** (student model):

```python
from uuid import UUID

from primer_sdk.models.student_model import PreferenceSignal
from primer_sdk.ports.student_model import CohortStrategyPort


class KMeansStrategy(CohortStrategyPort):
    @property
    def strategy_type(self) -> str:
        return 'kmeans_clustering'

    async def assign(self, user_id: UUID, signals: list[PreferenceSignal]) -> list[UUID]:
        # Compute feature vector from signals, find nearest cluster
        ...

    async def evolve(self, cohort_id: UUID, new_signals: list[PreferenceSignal]) -> dict:
        # Update cluster centroid with new data points
        ...

    async def should_reorganize(self, cohort_id: UUID) -> bool:
        # Check if intra-cluster variance exceeds threshold
        ...

    async def reorganize(self, org_id: UUID) -> dict:
        # Re-run k-means across all users
        ...
```

**Trigger scheduler** (cycle loop):

```python
from collections.abc import Callable
from typing import Any

from primer_sdk.models.cycle_loop import TriggerDefinition
from primer_sdk.ports.cycle_loop import TriggerSchedulerPort


class CronScheduler(TriggerSchedulerPort):
    async def schedule(self, trigger: TriggerDefinition) -> str:
        # Register cron job, return handle
        ...

    async def cancel(self, handle: str) -> None:
        ...

    async def list_active(self) -> list[dict[str, Any]]:
        ...

    async def register_webhook_handler(self, path: str, callback: Callable) -> None:
        ...
```

### 5. Test your adapter

Write tests against the port interface. The SDK includes tests that demonstrate the pattern:

```python
import pytest
from primer_sdk.ports.presentation import ChannelAdapterPort


class TestMyAdapter:
    def test_implements_port(self):
        adapter = TelegramAdapter(bot_token='test')
        assert isinstance(adapter, ChannelAdapterPort)

    @pytest.mark.asyncio
    async def test_send_event_buffers_tokens(self):
        adapter = TelegramAdapter(bot_token='test')
        session = make_test_session()
        await adapter.send_event(text_message_start_event(), session)
        await adapter.send_event(text_message_content_event('Hello'), session)
        await adapter.send_event(text_message_end_event(), session)
        assert adapter.last_sent_text == 'Hello'
```

See `tests/test_reference_slack.py` for a full example testing the reference Slack adapter.

## Extension Domains

### Student Model

Cohort-based preference aggregation. Users are grouped into evolving cohorts; preferences are resolved at the cohort level rather than individually.

| Port | Direction | Purpose |
|---|---|---|
| `IngestSignalPort` | Inbound | Receive preference signals |
| `QueryCohortPort` | Inbound | Query cohort preferences |
| `ManageCohortPort` | Inbound | CRUD on cohorts |
| `CohortStrategyPort` | Outbound | Clustering algorithm (main extension point) |
| `SignalStorePort` | Outbound | Signal persistence |
| `CohortStorePort` | Outbound | Cohort persistence |

Key models: `PreferenceSignal`, `Cohort`, `CohortSnapshot`, `MembershipEvent`, `IngestResult`

### Cycle Loop

Three composable layers for continuous AI operations: triggers (when), orchestrators (what), agent loops (how long).

| Port | Direction | Purpose |
|---|---|---|
| `RegisterTriggerPort` | Inbound | Manage trigger definitions |
| `RunOrchestratorPort` | Inbound | Execute workflow orchestrations |
| `RunAgentLoopPort` | Inbound | Run autonomous agent loops |
| `TriggerSchedulerPort` | Outbound | Scheduling engine (main extension point) |
| `WorkflowInvokerPort` | Outbound | Execute single workflows |
| `LoopStatePort` | Outbound | Agent loop state persistence |
| `OrchestrationStatePort` | Outbound | Orchestration state persistence |

Key models: `TriggerDefinition`, `OrchestrationPlan`, `AgentLoopDefinition`, `WorkflowResult`, `LoopIteration`

### Presentation Layer

Bidirectional channel adapters that translate AG-UI events to/from messaging platforms.

| Port | Direction | Purpose |
|---|---|---|
| `ChannelAdapterPort` | Outbound | Channel bridge (main extension point) |
| `ChannelSessionStorePort` | Outbound | Session mapping persistence |

Key models: `ChannelSession`, `ChannelMessage`, `ChannelFile`, `HitlGateConfig`

Reference implementation: `primer_sdk.reference.slack_adapter.SlackChannelAdapter`

## Contribution Guidelines

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Familiarity with Python ABCs and Pydantic v2

### Setup

```bash
git clone git@bitbucket.org:allogy/primer-sdk.git
cd primer-sdk
uv venv && uv sync --all-groups
uv run pytest tests/ -v          # verify baseline
```

### Development workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/<short-description>
   ```

2. **Implement your adapter** by subclassing the relevant port ABC. Place source files under `src/primer_sdk/` following the existing module structure.

3. **Write tests** in `tests/`. Follow the existing patterns:
   - Verify your class is a valid `isinstance` of the port
   - Test each abstract method implementation
   - Use `@pytest.mark.asyncio` for async tests
   - Use in-memory state for unit tests (no external services)

4. **Lint and format** before committing:
   ```bash
   uv run ruff check src/ tests/
   uv run ruff format src/ tests/
   ```

5. **Run the full test suite:**
   ```bash
   uv run pytest tests/ -v
   ```

6. **Commit** with conventional commit messages:
   ```
   feat: add Telegram channel adapter
   fix: handle empty message buffer in WhatsApp adapter
   test: add integration tests for cron trigger scheduler
   docs: update port contract docstrings
   ```

### Submission

Submissions should include:

1. **Architecture proposal** — a document covering:
   - Problem analysis and approach
   - System design with data flow diagrams
   - Port contract conformance (which ports you implement, how they interact)
   - Trade-off analysis
   - Scalability and failure mode considerations

2. **Proof of concept** — working code that:
   - Implements at least one port from the SDK
   - Includes tests that pass against the port interface
   - Demonstrates the core mechanism (can be against mock data)

Submit as a pull request to this repository, or as a separate repository that depends on this SDK.

### Code standards

- **Line length:** 100 characters
- **Quotes:** single quotes in source, double quotes acceptable
- **Type annotations:** required on all public methods
- **Imports:** absolute only, sorted by ruff
- **Async:** all port methods are async; implementations must be async
- **Dependencies:** do not add runtime dependencies beyond `pydantic`. Dev dependencies (testing tools, linters) go in `[project.optional-dependencies] dev`

### What not to modify

- `events.py` — the AG-UI event types are a fixed protocol contract
- `ports/platform.py` — these are extracted platform ABCs, not extension points
- Existing port ABCs — extend by implementing, not by modifying the interfaces
