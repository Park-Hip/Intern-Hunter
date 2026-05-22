# Agent Langfuse Tracing Upgrade Plan

## Objective

Upgrade agent tracing so Langfuse captures the real agent execution flow, not just the top-level question. The target outcome is one coherent trace for each `/agent/ask` request that includes:

- request-level lifecycle
- guardrail decision
- LangChain agent execution
- future tool calls without redesign

This plan does not implement code. It defines the intended file changes, sequencing, and verification.

## Current State

The current tracing path is too shallow:

- [src/agents/tracing.py](D:/Data_Science_Project/InternHunter/src/agents/tracing.py) manually creates a Langfuse trace with the user question and later updates it with a final status.
- [src/agents/runtime.py](D:/Data_Science_Project/InternHunter/src/agents/runtime.py) starts and finishes that manual trace around `agent.invoke(...)`.
- [src/agents/service.py](D:/Data_Science_Project/InternHunter/src/agents/service.py) does not create a request-level trace around guardrail, preview, and runtime branches.
- [src/agents/guardrail.py](D:/Data_Science_Project/InternHunter/src/agents/guardrail.py) is not traced.
- LangChain execution is not wired to Langfuse's official `CallbackHandler`, so Langfuse does not see the actual agent steps.

## Desired End State

Each `/agent/ask` request should produce:

1. one request/root trace
2. one traced guardrail observation
3. nested LangChain/LangGraph execution via Langfuse callback integration
4. one stable `trace_id` returned in API metadata
5. fail-open behavior when Langfuse is not configured

## Official Direction To Follow

Based on official Langfuse docs:

- LangChain tracing should use `langfuse.langchain.CallbackHandler`
- non-LangChain boundaries should use Langfuse SDK observations/spans
- request/session metadata should be attached consistently at invocation time

## File Plan

### 1. [src/agents/tracing.py](D:/Data_Science_Project/InternHunter/src/agents/tracing.py)

**Modify heavily**

This should become the central tracing seam for the agent layer.

Planned responsibilities:

- initialize Langfuse client from typed settings
- create a request/root trace context
- create one LangChain `CallbackHandler` per invocation
- expose a traced guardrail observation helper
- finish the request trace cleanly
- preserve `NullAgentTracer` fail-open behavior

Likely refactor direction:

- replace the current `start_trace(question)` / `finish_trace(trace_id, status)` abstraction
- introduce request-scoped tracing methods instead of question-only trace methods

### 2. [src/agents/service.py](D:/Data_Science_Project/InternHunter/src/agents/service.py)

**Modify**

This should own the request-level tracing lifecycle.

Planned responsibilities:

- start the request trace as soon as an agent request enters the service layer
- trace the guardrail decision as a child observation
- finish blocked requests with refusal status
- finish preview requests with preview status
- pass trace context into the runtime for allowed requests
- finish allowed requests with `ok`

### 3. [src/agents/runtime.py](D:/Data_Science_Project/InternHunter/src/agents/runtime.py)

**Modify**

This should stop being the only owner of tracing and instead consume request-scoped tracing helpers.

Planned responsibilities:

- obtain LangChain callback handler from the tracer
- merge callback config with memory/session config
- pass Langfuse callback config into `agent.invoke(...)`
- return the request trace id provided by the tracing layer

### 4. [src/agents/guardrail.py](D:/Data_Science_Project/InternHunter/src/agents/guardrail.py)

**Prefer no major change**

Keep `screen_question()` as a pure decision function if possible.

Preferred tracing approach:

- wrap it from the service/tracing layer
- avoid decorating every helper directly unless the wrapper approach becomes awkward

### 5. [tests/unit/test_agent_tracing.py](D:/Data_Science_Project/InternHunter/tests/unit/test_agent_tracing.py)

**Modify**

Expand coverage to include:

- request/root trace lifecycle
- callback handler creation
- guardrail observation behavior
- Langfuse disabled/fail-open behavior
- trace id propagation

### 6. [tests/unit/test_agent_runtime.py](D:/Data_Science_Project/InternHunter/tests/unit/test_agent_runtime.py)

**Modify**

Expand coverage to include:

- callback handler wiring into `agent.invoke(...)`
- merge of memory config and tracing config
- stable `trace_id` propagation through runtime output

### 7. [tests/integration/test_agent_api.py](D:/Data_Science_Project/InternHunter/tests/integration/test_agent_api.py)

**Modify**

Add or refine end-to-end assertions for:

- blocked requests still include trace metadata
- preview requests still include trace metadata
- allowed requests still include trace metadata
- trace metadata shape remains stable for API consumers

## Execution Phases

## Phase 1: Refactor Tracing Interface

Goal:

- move from manual question-only tracing to request-scoped tracing

Tasks:

- redesign the tracer interface in `src/agents/tracing.py`
- support root trace creation and completion
- support LangChain callback creation
- support guardrail child observation
- preserve fail-open null tracer behavior

Done when:

- the tracer abstraction can support blocked, preview, and allowed request paths

## Phase 2: Trace The Request Lifecycle In Service

Goal:

- make `/agent/ask` request handling traceable as one flow

Tasks:

- start request trace in `service.py`
- wrap guardrail evaluation in a traced observation
- finish blocked and preview paths explicitly
- pass request trace context into runtime

Done when:

- every request branch can be represented under one request trace

## Phase 3: Wire Langfuse Into LangChain Runtime

Goal:

- trace real LangChain execution with official Langfuse integration

Tasks:

- create per-invocation Langfuse callback handler
- pass callback config into `agent.invoke(...)`
- combine callback config with memory/session config

Done when:

- runtime invocation is traced by Langfuse through LangChain, not only by manual top-level trace creation

## Phase 4: Tighten Tests

Goal:

- prove the new tracing model without relying on live Langfuse access

Tasks:

- update unit tests for tracer behavior
- update runtime tests for callback/config injection
- update integration tests for trace metadata continuity

Done when:

- tracing-specific unit and integration tests pass on the local tree

## Phase 5: Optional Docs Sync

Goal:

- keep docs truthful if the visible tracing behavior changes

Likely doc touch points:

- [docs/current-system/current_behavior.md](D:/Data_Science_Project/InternHunter/docs/current-system/current_behavior.md)
- [docs/api/overview.md](D:/Data_Science_Project/InternHunter/docs/api/overview.md)
- [README.md](D:/Data_Science_Project/InternHunter/README.md)

Only update these if:

- API-visible trace metadata changes
- developer tracing setup instructions change

## Testing Strategy

### Smallest relevant test commands

```powershell
uv run pytest tests/unit/test_agent_tracing.py -v
uv run pytest tests/unit/test_agent_runtime.py -v
uv run pytest tests/integration/test_agent_api.py -v
```

If service behavior changes enough to affect route-level expectations:

```powershell
uv run pytest tests/unit/test_agent_api_routes.py -v
```

### Manual verification after implementation

If Langfuse is configured:

1. send a blocked request
2. send a preview request
3. send an allowed request
4. verify Langfuse shows:
   - request/root trace
   - guardrail observation
   - LangChain nested execution for the allowed request

## Risks

### Duplicate traces

If manual tracing and callback tracing are both kept in parallel, traces may fragment.

Mitigation:

- move to one root trace model with nested callback tracing

### Over-instrumentation

Tracing too many small helpers will make traces noisy.

Mitigation:

- observe only request-level and guardrail-level non-LangChain boundaries

### Incorrect callback reuse

Reusing one handler across requests can create bad state.

Mitigation:

- create callback handler per request or per invocation

### Sensitive input duplication

Automatic observation capture can record more input/output than necessary.

Mitigation:

- keep non-LangChain observation scope narrow
- prefer controlled observation boundaries over broad decoration

### Fail-open regressions

Tracing must not break the API when Langfuse is absent.

Mitigation:

- preserve and test `NullAgentTracer`

## Final Decision On `@observe`

Yes, Langfuse `@observe`-style tracing should be added for non-LangChain calls, including the guardrail.

But it should be applied narrowly:

- yes for request/service orchestration
- yes for guardrail decision boundary
- no for every small utility/helper

The main tracing mechanism for agent execution itself should still be Langfuse's official LangChain `CallbackHandler`.

## Suggested Commit Slices

1. `refactor: redesign agent tracer around request-scoped tracing`
2. `feat: wire langfuse callback handler into langchain runtime`
3. `feat: trace guardrail and request lifecycle`
4. `test: cover langfuse callback and guardrail tracing behavior`
