# Langfuse v3 Tracing Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore real Langfuse tracing for `POST /agent/ask` by updating the agent tracing code to the Langfuse v3 SDK model and wiring LangChain callback tracing through the actual LangGraph invocation path.

**Architecture:** Keep one request-scoped trace per `/agent/ask` request, record the guardrail as a child observation, and pass a Langfuse LangChain `CallbackHandler` into the compiled LangGraph agent through the `config=` argument. Replace the current old-SDK `trace()` / `span()` assumptions with Langfuse v3 span/observation APIs while preserving fail-open behavior when Langfuse is not configured.

**Tech Stack:** FastAPI, LangChain, LangGraph, Langfuse v3, pytest, Pydantic

---

## File Structure

### Files to modify

- `src/agents/tracing.py`
  - Replace old Langfuse SDK usage with Langfuse v3 request-span and guardrail-observation handling.
- `src/agents/runtime.py`
  - Pass LangChain callback config via `agent.invoke(..., config=...)` instead of putting `config` inside the input payload.
- `src/agents/service.py`
  - Keep request-scoped tracing ownership here, but adjust only if the new trace context API shape needs small plumbing changes.
- `tests/unit/test_agent_tracing.py`
  - Rewrite tests so they validate the Langfuse v3 contract instead of the removed `trace()` / `span()` contract.
- `tests/unit/test_agent_runtime.py`
  - Assert the runtime passes callback config through the separate `config=` argument.
- `tests/integration/test_agent_api.py`
  - Keep response-level trace assertions and add one focused assertion that the allowed path still returns the request trace ID.
- `docs/getting-started/setup.md`
  - Clarify that Langfuse tracing depends on valid Langfuse credentials and a working v3 tracing path.
- `docs/current-system/current_behavior.md`
  - Update only if the implementation wording currently overstates what tracing does today.

### Files likely not to change

- `src/agents/guardrail.py`
  - Keep the guardrail logic itself unchanged; trace it from the tracer/service boundary.
- `src/internhunter/config/settings.py`
  - No config-model change is needed unless the fix reveals a missing Langfuse setting.

---

### Task 1: Lock In the Failing Behavior With Realistic Tests

**Files:**
- Modify: `tests/unit/test_agent_tracing.py`
- Modify: `tests/unit/test_agent_runtime.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write a failing tracer test for the Langfuse v3 request-span contract**

Add a test that expects the tracer to use `start_as_current_span(...)` and `start_as_current_observation(...)`, not `trace(...)` / `span(...)`.

```python
def test_langfuse_request_context_uses_v3_request_span_and_guardrail_observation(monkeypatch) -> None:
    class _FakeRequestSpan:
        def __init__(self) -> None:
            self.trace_id = "trace-real-v3"
            self.id = "span-real-v3"
            self.update_calls: list[dict[str, object]] = []

        def update_trace(self, **kwargs) -> None:
            self.update_calls.append(kwargs)

    class _FakeGuardrailObservation:
        def __init__(self) -> None:
            self.end_calls: list[dict[str, object]] = []

        def end(self, **kwargs) -> None:
            self.end_calls.append(kwargs)

    class _FakeContextManager:
        def __init__(self, value) -> None:
            self.value = value

        def __enter__(self):
            return self.value

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _FakeLangfuse:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.request_span = _FakeRequestSpan()
            self.guardrail = _FakeGuardrailObservation()
            self.start_as_current_span_calls: list[dict[str, object]] = []
            self.start_as_current_observation_calls: list[dict[str, object]] = []
            self.flush_calls = 0

        def start_as_current_span(self, **kwargs):
            self.start_as_current_span_calls.append(kwargs)
            return _FakeContextManager(self.request_span)

        def start_as_current_observation(self, **kwargs):
            self.start_as_current_observation_calls.append(kwargs)
            return _FakeContextManager(self.guardrail)

        def flush(self) -> None:
            self.flush_calls += 1
```

- [ ] **Step 2: Run the tracer test to verify it fails against the current implementation**

Run:

```powershell
uv run python -m pytest tests/unit/test_agent_tracing.py -v
```

Expected:
- FAIL because the current code still expects `client.trace(...)`, `client.span(...)`, and `trace.get_langchain_handler(...)`.

- [ ] **Step 3: Write a failing runtime test that proves callback config must be passed as `config=`**

Add or update a test like this:

```python
def test_agent_runtime_passes_tracing_config_via_invoke_config_argument() -> None:
    calls: list[tuple[dict[str, object], dict[str, object] | None]] = []

    class _FakeAgent:
        def invoke(self, payload, config=None, **kwargs):
            calls.append((payload, config))
            return {"messages": [{"role": "assistant", "content": "hello"}]}
```

Key assertions:
- `payload == {"messages": [...]}`
- `config["callbacks"]` exists
- `config["configurable"]["thread_id"]` still exists for memory
- `payload` does **not** contain a nested `"config"` key

- [ ] **Step 4: Run the runtime test to verify it fails before the code change**

Run:

```powershell
uv run python -m pytest tests/unit/test_agent_runtime.py -v
```

Expected:
- FAIL because the current runtime pushes `config` into the input payload instead of the separate invoke argument.

- [ ] **Step 5: Commit the failing tests**

```bash
git add tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py
git commit -m "test: capture langfuse v3 tracing regressions"
```

---

### Task 2: Rewrite `src/agents/tracing.py` for Langfuse v3

**Files:**
- Modify: `src/agents/tracing.py`
- Test: `tests/unit/test_agent_tracing.py`

- [ ] **Step 1: Replace old trace/span usage with a request-scoped v3 span model**

Refactor `LangfuseTraceContext` to store:

```python
class LangfuseTraceContext:
    def __init__(
        self,
        client: Any,
        request_span: Any,
        callback_handler: Any | None,
        question: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self.client = client
        self.request_span = request_span
        self.callback_handler = callback_handler
        self.question = question
        self.session_id = session_id
        self.user_id = user_id
        self.trace_id = str(getattr(request_span, "trace_id", "")) or f"agent-trace-{uuid4()}"
        self.root_span_id = str(getattr(request_span, "id", "")) or None
```

- [ ] **Step 2: Build the LangChain callback handler with the official v3 path**

Use the official import:

```python
from langfuse.langchain import CallbackHandler
```

Construct it per request using the current trace context:

```python
callback_handler = CallbackHandler(
    trace_context={
        "trace_id": request_span.trace_id,
        "parent_span_id": request_span.id,
    }
)
```

Then return it from `build_langchain_config()`:

```python
def build_langchain_config(self) -> dict[str, Any]:
    metadata = {
        "langfuse_session_id": self.session_id,
        "langfuse_user_id": self.user_id,
    }
    filtered_metadata = {k: v for k, v in metadata.items() if v is not None}

    config: dict[str, Any] = {"callbacks": [self.callback_handler]}
    if filtered_metadata:
        config["metadata"] = filtered_metadata
    return config
```

- [ ] **Step 3: Record the guardrail as a Langfuse v3 observation**

Replace `client.span(...)` with:

```python
with self.client.start_as_current_observation(
    trace_context={"trace_id": self.trace_id, "parent_span_id": self.root_span_id},
    name="agent.guardrail",
    as_type="guardrail",
    input={"question": question},
    metadata=metadata,
) as observation:
    observation.end(output=output)
```

- [ ] **Step 4: Finish the request trace using the request span**

Replace `self.trace.update(...)` with:

```python
def finish(self, status: str) -> None:
    try:
        self.request_span.update_trace(output={"status": status})
        self.client.flush()
    except Exception:
        return None
```

- [ ] **Step 5: Start the request with `start_as_current_span(...)`**

Refactor `LangfuseAgentTracer.start_request(...)` to do:

```python
request_span_cm = self.client.start_as_current_span(
    name="agent.ask",
    input={"question": question},
    metadata={"component": "internhunter-agent-runtime"},
)
request_span = request_span_cm.__enter__()
```

Store the context manager on the trace context so `finish()` can close it:

```python
self._request_span_cm = request_span_cm
```

and in `finish()`:

```python
try:
    self.request_span.update_trace(
        output={"status": status},
        session_id=self.session_id,
        user_id=self.user_id,
    )
finally:
    self._request_span_cm.__exit__(None, None, None)
    self.client.flush()
```

- [ ] **Step 6: Preserve fail-open behavior**

Keep the outer exception handling in `start_request(...)`:

```python
except Exception:
    return NullTraceContext(trace_id=f"agent-trace-{uuid4()}")
```

Do not remove fail-open behavior in this task.

- [ ] **Step 7: Run the tracer tests**

Run:

```powershell
uv run python -m pytest tests/unit/test_agent_tracing.py -v
```

Expected:
- PASS

- [ ] **Step 8: Commit**

```bash
git add src/agents/tracing.py tests/unit/test_agent_tracing.py
git commit -m "fix: migrate agent tracing to langfuse v3 sdk"
```

---

### Task 3: Pass LangChain Tracing Through the Real LangGraph Invoke Path

**Files:**
- Modify: `src/agents/runtime.py`
- Test: `tests/unit/test_agent_runtime.py`

- [ ] **Step 1: Update the runtime invoke call to use the separate `config=` argument**

Replace:

```python
invocation_payload["config"] = invocation_config
response = self.agent.invoke(invocation_payload)
```

with:

```python
response = self.agent.invoke(
    invocation_payload,
    config=invocation_config or None,
)
```

- [ ] **Step 2: Keep the payload clean**

The payload should remain:

```python
invocation_payload = {"messages": messages}
```

Do not embed callback or memory settings inside the payload dict.

- [ ] **Step 3: Keep merged memory + tracing config intact**

The merged config should still combine:

```python
{
    "configurable": {"thread_id": payload.session_id},
    "callbacks": [callback_handler],
    "metadata": {
        "langfuse_session_id": payload.session_id,
        "langfuse_user_id": payload.user_id,
    },
}
```

No separate fix is needed in `_merge_agent_configs(...)` unless the tests show a conflict.

- [ ] **Step 4: Run the runtime tests**

Run:

```powershell
uv run python -m pytest tests/unit/test_agent_runtime.py -v
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/runtime.py tests/unit/test_agent_runtime.py
git commit -m "fix: pass langfuse callback config through langgraph invoke"
```

---

### Task 4: Verify the Service Flow Still Returns Stable Trace Metadata

**Files:**
- Modify: `tests/integration/test_agent_api.py`
- Modify: `src/agents/service.py` (only if a small trace-context lifecycle fix is needed)

- [ ] **Step 1: Add one integration test that the allowed path preserves request-scoped tracing**

Add a focused test like:

```python
def test_agent_api_allowed_request_returns_request_scoped_trace_id(monkeypatch):
    class _FakeTraceContext:
        trace_id = "request-trace-1"

        def record_guardrail(self, question, decision):
            return None

        def build_langchain_config(self):
            return {}

        def finish(self, status):
            return None
```

Make the fake runtime return the same `trace_id` and assert the response metadata includes it.

- [ ] **Step 2: Run the integration tests**

Run:

```powershell
uv run python -m pytest tests/integration/test_agent_api.py -v
```

Expected:
- PASS

- [ ] **Step 3: Only adjust `service.py` if needed**

If the new tracer lifecycle requires a small close-order fix, keep it tiny and local. Do not redesign the service branching.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_agent_api.py src/agents/service.py
git commit -m "test: verify request-scoped trace ids across agent api paths"
```

---

### Task 5: Do a Focused End-to-End Verification Pass

**Files:**
- No required code changes unless verification exposes one

- [ ] **Step 1: Run the focused automated suite**

Run:

```powershell
uv run python -m pytest tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py tests/unit/test_agent_api_routes.py tests/integration/test_agent_api.py -v
```

Expected:
- All tests PASS

- [ ] **Step 2: Run an import sanity check**

Run:

```powershell
uv run python -c "from src.internhunter.api.app import app; print(app.title)"
uv run python -c "from src.agents.tracing import build_agent_tracer; print(type(build_agent_tracer()).__name__)"
```

Expected:
- app imports successfully
- tracer factory returns `LangfuseAgentTracer` when keys are configured

- [ ] **Step 3: Run one live manual API smoke**

Start the app:

```powershell
uv run python -m uvicorn src.internhunter.api.app:app --reload
```

Then hit:

```json
{
  "question": "What can you do?",
  "session_id": "trace-smoke-1"
}
```

Verify:
- response contains `metadata.trace_id`
- a trace appears in Langfuse Cloud
- the trace includes:
  - root request span
  - guardrail observation
  - nested LangChain execution

- [ ] **Step 4: If the live smoke fails, capture the exact failure point before changing code**

Use one targeted diagnostic only:
- does `start_request()` return `NullTraceContext`?
- does the trace exist without nested LangChain steps?
- does the trace exist but miss the guardrail observation?

Do not bundle a second redesign into this pass.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "test: verify langfuse tracing end to end"
```

---

### Task 6: Sync Docs to the Verified Tracing Behavior

**Files:**
- Modify: `docs/getting-started/setup.md`
- Modify: `docs/current-system/current_behavior.md`
- Modify: `README.md` (only if tracing setup or behavior is described there)

- [ ] **Step 1: Update setup docs with the actual tracing prerequisites**

Document:
- Langfuse v3-compatible dependency set is required
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` must be configured
- traces fail open when config is missing

Suggested wording block:

```md
Agent tracing uses Langfuse v3. With valid Langfuse credentials configured, `/agent/ask` emits a request-level trace, a guardrail observation, and nested LangChain execution. If Langfuse is not configured or the backend is unavailable, the API still returns a local `trace_id` but no remote trace is created.
```

- [ ] **Step 2: Make live behavior docs precise**

In `docs/current-system/current_behavior.md`, avoid vague wording like “tracing is live” unless the live smoke in Task 5 actually passed.

If Task 5 live smoke passes, document:
- request trace
- guardrail observation
- nested LangChain tracing

If Task 5 live smoke fails, document only:
- request trace seam exists
- fail-open local trace IDs still exist

- [ ] **Step 3: Run a docs consistency grep**

Run:

```powershell
rg -n "Langfuse|trace_id|runtime-backed|guardrail|nested LangChain" README.md docs
```

Expected:
- docs reflect the verified tracing behavior
- no stale wording claims tracing is richer than what was proven

- [ ] **Step 4: Commit**

```bash
git add README.md docs/getting-started/setup.md docs/current-system/current_behavior.md
git commit -m "docs: clarify verified langfuse tracing behavior"
```

---

## Self-Review

### Spec coverage
- Root cause 1 addressed: old Langfuse SDK API mismatch in `src/agents/tracing.py`
- Root cause 2 addressed: wrong LangGraph callback config plumbing in `src/agents/runtime.py`
- Guardrail observation included
- Fail-open behavior preserved
- Tests and live verification included
- Docs sync included

### Placeholder scan
- No `TODO` / `TBD`
- Each task includes exact file targets
- Each test/verification step includes commands
- Each code step includes concrete target snippets

### Type consistency
- `trace_context` remains the runtime/service seam
- `build_langchain_config()` remains the callback-config hook
- `finish(status)` remains the request close hook
- callback wiring consistently targets `agent.invoke(..., config=...)`

