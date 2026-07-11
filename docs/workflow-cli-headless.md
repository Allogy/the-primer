# Workflow CLI Headless Automation

`src/primer_core/wdfs/tutor-concept.yaml` is a workflow-cli-compatible WDF for running one Primer tutoring assessment without terminal prompts.

Validate the WDF from the monorepo `workflow-cli/` checkout:

```bash
uv run workflow validate ../the-primer/src/primer_core/wdfs/tutor-concept.yaml
```

Push it before remote execution:

```bash
uv run workflow push ../the-primer/src/primer_core/wdfs/tutor-concept.yaml
```

Run it headlessly with the example input payload:

```bash
uv run workflow run tutor-concept \
  --input @../the-primer/examples/workflow-cli/tutor-concept.input.json \
  --stream \
  --json \
  --no-color
```

The workflow has a single `structured_input` gate. `workflow run --input` auto-submits that gate, and `--json --no-color` keeps output suitable for CI logs or other agents.

## Using WorkflowClient As The Primer Port

Primer code should depend on the SDK port (`RunWorkflowPort`), not on workflow-cli commands. For local tools or automation, wrap a workflow-cli-compatible client instance with `RunWorkflowClientPort`:

```python
from cli.client import WorkflowClient

from primer_core.workflow_cli import RunWorkflowClientPort

client = WorkflowClient(host="https://api.example.com", api_key="...", org_id="...")
runner = RunWorkflowClientPort(client)
```

`runner` can then be passed to `EngagementOrchestrator(..., runner=runner, ...)`. The adapter starts the workflow, polls status, auto-submits the first `INPUT` gate from `RunWorkflowRequest.input_data`, and returns SDK `RunWorkflowResponse` data with final `node_outputs`.
