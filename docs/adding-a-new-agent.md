# Adding A New Agent

This guide describes how to add a runtime agent to the current OpenAlpha orchestrator.

## 1. Subclass `BaseAgent`

Create a new module under `backend/app/agents/` and subclass `BaseAgent`.

Minimum structure:

```python
from backend.app.agents.base import AgentExecutionPayload, BaseAgent


class MyAgent(BaseAgent[MyOutputSchema]):
    name = "my_agent_name"
    output_schema = MyOutputSchema

    async def execute(self, context):
        ...
        return AgentExecutionPayload(
            status="completed",
            provider="local",
            model="deterministic",
            output=output,
            data_used=["field_a"],
            warnings=[],
        )
```

Requirements:

- define `name`
- define `output_schema` unless raw dict output is intentional
- implement `execute(context)`

## 2. Define Or Reuse A Schema

Add a Pydantic schema to `backend/app/orchestrator/schemas.py` if the agent needs a new structured output type.

Keep the schema:

- explicit
- JSON-safe
- independent from provider-specific raw response shapes

If the output should live on `AnalysisContext`, add a new context field there too.

## 3. Decide How The Agent Runs

Choose whether the agent is:

- deterministic only
- LLM-backed
- hybrid with deterministic fallback

If LLM-backed:

- use a provider implementing `BaseLLMProvider`
- prefer `generate_json()` for structured outputs
- catch non-fatal LLM failures and return a deterministic fallback when appropriate

## 4. Wire The Agent Into The Orchestrator

Update `AnalysisRunner` in `backend/app/orchestrator/base.py`.

Required changes:

- add the agent instance to `self.agents`
- schedule it in the desired stage order
- if it creates a new context output field, add the mapping to `RUNTIME_OUTPUT_FIELDS`

If you skip the `RUNTIME_OUTPUT_FIELDS` update for a new context-backed output, the orchestrator will not automatically sync `result.output` into the runtime context.

## 5. Emit Warnings And Statuses Correctly

Use statuses intentionally:

- `completed` when the agent produced its intended output
- `partial` when useful output exists but is degraded
- `failed` when no reliable output could be produced

Warnings should describe:

- missing upstream data
- provider degradation
- fallback usage
- stale or partial evidence

Fatal vs non-fatal behavior:

- non-fatal issues should usually return `partial` output where possible
- fatal auth/quota/configuration failures can bubble up and stop the run

## 6. Record Cost Traces Properly

`BaseAgent.run()` automatically appends a `CostTrace` from the returned payload.

To keep cost reporting accurate:

- return the real provider/model used
- return input/output token counts when available
- return `estimated_cost_usd`

For deterministic steps, use:

- `provider="local"`
- `model="deterministic"`

## 7. Avoid Provider-Specific Leakage

Do not expose raw OpenAI or other provider response shapes in agent outputs.

Agent outputs should stay stable even if the backing provider changes.

Bad pattern:

- storing raw provider response objects directly in an output schema

Good pattern:

- normalize to a repo-owned schema and preserve raw provider detail only in logs or internal traces if needed

## 8. Persisted Output Expectations

Every agent result may be persisted into:

- `agent_outputs.output_json`
- `cost_traces`

Make sure the output is serializable and useful when later reviewed from report detail pages or debugging tools.

## 9. Tests To Add

Add focused tests under `backend/tests/`.

Typical coverage:

- happy path output validation
- missing-input partial behavior
- non-fatal LLM fallback behavior
- fatal LLM error behavior if applicable
- orchestrator integration if stage order or context sync changes

Existing tests in this repo already show the pattern for agent-level and API-level coverage.

## 10. Docs To Update

When adding an agent, update:

- [docs/agents.md](/C:/Users/ernos/OpenAlpha/docs/agents.md)
- [docs/architecture.md](/C:/Users/ernos/OpenAlpha/docs/architecture.md) if the graph changes
- [README.md](/C:/Users/ernos/OpenAlpha/README.md) if user-visible behavior changes

Docs should describe current behavior and explicitly label anything still planned.
