# Simple Langfuse Agent Tracing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify agent tracing so `src/agents/tracing.py` uses the smallest maintainable Langfuse + LangChain setup that still traces LangChain runs, attaches `user_id` and `session_id`, captures question and answer, and records the guardrail step.

**Architecture:** Keep tracing in `src/agents/` and stop building a large custom request-tracing framework around Langfuse. Use Langfuse’s official `CallbackHandler` as the primary LangChain tracing mechanism, keep one tiny helper that builds LangChain callback config from the request payload, and add one small Langfuse SDK observation helper for the non-LangChain guardrail step. Preserve fail-open behavior when Langfuse is unconfigured.

**Tech Stack:** FastAPI, LangChain, LangGraph, Langfuse v3, pytest, Pydantic

---

## File Structure

### Files to modify

- `src/agents/tracing.py`
  - Collapse the current tracer/context abstraction into a small Langfuse integration module that builds callback config and records one optional guardrail observation.
- `src/agents/runtime.py`
  - Keep runtime invocation simple: ask tracing for LangChain config and pass it to `agent.invoke(..., config=...)`.
- `src/agents/service.py`
  - Keep service ownership of guardrail flow, but simplify how it calls tracing before and after the guardrail.
- `tests/unit/test_agent_tracing.py`
  - Replace the current request-span lifecycle-heavy tests with tests for the simpler callback-config + guardrail-observation contract.
- `tests/unit/test_agent_runtime.py`
  - Keep one focused assertion that the runtime passes LangChain callback config and metadata correctly.
- `tests/integration/test_agent_api.py`
  - Keep response-level `trace_id` checks and guardrail-path behavior checks aligned with the simplified tracer.
- `docs/getting-started/setup.md`
  - Clarify the simple Langfuse requirements.
- `docs/current-system/current_behavior.md`
  - Clarify what is actually traced now.
- `docs/operations/monitoring.md`
  - Keep the monitoring note aligned with the simplified tracing shape.

### Files not to create

- Do **not** create `src/internhunter/observability/tracing.py`
- Do **not** add a new generic observability subsystem for this cleanup

### Files likely not to change

- `src/agents/guardrail.py`
  - Keep guardrail logic unchanged; trace it from the service/tracing boundary.
- `src/internhunter/config/settings.py`
  - No config-model redesign is needed; keep using `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST`.

---

### Task 1: Replace the Current Tracing Contract With Simpler Tests

**Files:**
- Modify: `tests/unit/test_agent_tracing.py`
- Modify: `tests/unit/test_agent_runtime.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write a failing tracer test for the simplified callback-config API**

Replace the current “request trace context” expectation with a smaller contract:

```python
def test_build_langchain_tracing_config_returns_callbacks_and_metadata(monkeypatch) -> None:
    class _FakeCallbackHandler:
        pass

    class _FakeLangfuseModule:
        CallbackHandler = _FakeCallbackHandler

    monkeypatch.setitem(sys.modules, "langfuse.langchain", _FakeLangfuseModule)

    config = build_langchain_tracing_config(
        user_id="user-1",
        session_id="session-1",
    )

    assert len(config["callbacks"]) == 1
    assert isinstance(config["callbacks"][0], _FakeCallbackHandler)
    assert config["metadata"] == {
        "langfuse_user_id": "user-1",
        "langfuse_session_id": "session-1",
    }
```

- [ ] **Step 2: Write a failing tracer test for unconfigured fail-open behavior**

```python
def test_build_langchain_tracing_config_returns_empty_when_langfuse_is_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.agents.tracing.settings",
        type(
            "_FakeSettings",
            (),
            {
                "LANGFUSE_PUBLIC_KEY": None,
                "LANGFUSE_SECRET_KEY": None,
                "LANGFUSE_HOST": None,
            },
        )(),
    )

    assert build_langchain_tracing_config(user_id=None, session_id=None) == {}
```

- [ ] **Step 3: Write a failing guardrail tracing test for one small observation helper**

```python
def test_trace_guardrail_decision_records_one_guardrail_observation(monkeypatch) -> None:
    class _FakeObservation:
        def __init__(self) -> None:
            self.end_calls = []

        def end(self, **kwargs) -> None:
            self.end_calls.append(kwargs)

    class _FakeContextManager:
        def __init__(self, observation) -> None:
            self.observation = observation

        def __enter__(self):
            return self.observation

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _FakeClient:
        def __init__(self) -> None:
            self.calls = []
            self.observation = _FakeObservation()

        def start_as_current_observation(self, **kwargs):
            self.calls.append(kwargs)
            return _FakeContextManager(self.observation)
```

Assertion target:
- observation type is `guardrail`
- input contains the user question
- metadata/output reflect allow/refuse decision

- [ ] **Step 4: Write a failing runtime test for the simpler tracing helper**

```python
def test_agent_runtime_passes_simple_langchain_tracing_config() -> None:
    calls = []

    class _FakeAgent:
        def invoke(self, payload, config=None, **kwargs):
            calls.append((payload, config))
            return {"messages": [{"role": "assistant", "content": "ok"}]}
```

Patch the tracing helper and assert:

```python
assert calls == [
    (
        {"messages": [{"role": "user", "content": "hello"}]},
        {
            "callbacks": ["handler"],
            "metadata": {
                "langfuse_user_id": "user-1",
                "langfuse_session_id": "session-1",
            },
        },
    )
]
```

- [ ] **Step 5: Run the focused failing tests**

Run:

```powershell
uv run python -m pytest tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py -v
```

Expected:
- FAIL because the current code still expects a richer request-trace context abstraction.

- [ ] **Step 6: Commit the failing tests**

```bash
git add tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py
git commit -m "test: capture simpler langfuse tracing contract"
```

---

### Task 2: Simplify `src/agents/tracing.py`

**Files:**
- Modify: `src/agents/tracing.py`
- Test: `tests/unit/test_agent_tracing.py`

- [ ] **Step 1: Replace the custom tracer/context abstraction with a tiny module API**

Reduce `src/agents/tracing.py` to a small surface like:

```python
def build_langchain_tracing_config(
    *,
    user_id: str | None,
    session_id: str | None,
) -> dict[str, Any]:
    ...


def trace_guardrail_decision(
    *,
    question: str,
    allowed: bool,
    refusal_category: str | None = None,
    refusal_code: str | None = None,
) -> str:
    ...
```

Keep one helper for generating a local fallback trace id when Langfuse is absent:

```python
def build_local_trace_id() -> str:
    return f"agent-trace-{uuid4()}"
```

- [ ] **Step 2: Build the LangChain callback config using the official docs path**

Use:

```python
from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler
```

And follow the simple docs path:

```python
Langfuse(
    public_key=public_key,
    secret_key=secret_key,
    host=host,
)
handler = CallbackHandler()
```

Then return:

```python
return {
    "callbacks": [handler],
    "metadata": {
        "langfuse_user_id": user_id,
        "langfuse_session_id": session_id,
    },
}
```

Filter out `None` values before returning metadata.

- [ ] **Step 3: Keep fail-open behavior tiny**

If credentials are missing or handler creation fails:

```python
return {}
```

Do not create a custom null tracer class.

- [ ] **Step 4: Implement one small guardrail observation helper**

Use the Langfuse SDK only for this non-LangChain step:

```python
langfuse = get_client()
with langfuse.start_as_current_observation(
    as_type="guardrail",
    name="agent.guardrail",
    input={"question": question},
    metadata=metadata,
) as observation:
    observation.end(output=output)
```

If tracing is unavailable or the SDK call fails:

```python
return build_local_trace_id()
```

If tracing is configured and active:
- return `langfuse.get_current_trace_id()` if available
- otherwise fall back to a local trace id

- [ ] **Step 5: Do not add custom tracing for every helper**

Specifically avoid:
- request-scoped trace context classes
- custom callback wrapper classes
- custom trace/span lifecycle managers
- tracing every guardrail helper

Keep only:
- callback-config builder
- guardrail observation helper
- local trace-id fallback

- [ ] **Step 6: Run the tracer tests**

Run:

```powershell
uv run python -m pytest tests/unit/test_agent_tracing.py -v
```

Expected:
- PASS

- [ ] **Step 7: Commit**

```bash
git add src/agents/tracing.py tests/unit/test_agent_tracing.py
git commit -m "refactor: simplify langfuse tracing integration"
```

---

### Task 3: Simplify Runtime Wiring

**Files:**
- Modify: `src/agents/runtime.py`
- Test: `tests/unit/test_agent_runtime.py`

- [ ] **Step 1: Remove request-trace context plumbing from the runtime**

Simplify the runtime method signature from:

```python
def invoke(self, payload: AgentRuntimeInput, trace_context: AgentTraceContext | None = None) -> AgentRuntimeOutput:
```

to:

```python
def invoke(self, payload: AgentRuntimeInput) -> AgentRuntimeOutput:
```

- [ ] **Step 2: Ask tracing for LangChain config directly**

Inside `invoke(...)`:

```python
invocation_config = _merge_agent_configs(
    self.memory.build_invocation_config(payload.session_id),
    build_langchain_tracing_config(
        user_id=payload.user_id,
        session_id=payload.session_id,
    ),
)
```

- [ ] **Step 3: Keep the invoke call simple**

```python
response = self.agent.invoke(
    {"messages": messages},
    config=invocation_config or None,
)
```

- [ ] **Step 4: Keep trace id output simple**

For the runtime output, use the current active Langfuse trace id if available; otherwise fall back:

```python
trace_id = get_current_trace_id_or_fallback()
```

Then:

```python
return AgentRuntimeOutput(
    summary=summary,
    warnings=[],
    trace_id=trace_id,
)
```

- [ ] **Step 5: Run the runtime tests**

Run:

```powershell
uv run python -m pytest tests/unit/test_agent_runtime.py -v
```

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git add src/agents/runtime.py tests/unit/test_agent_runtime.py
git commit -m "refactor: simplify runtime langfuse callback wiring"
```

---

### Task 4: Keep Guardrail Tracing in the Service Layer

**Files:**
- Modify: `src/agents/service.py`
- Modify: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Trace the guardrail from the service boundary**

After:

```python
guardrail = screen_question(artifact.question)
```

call:

```python
trace_id = trace_guardrail_decision(
    question=artifact.question,
    allowed=guardrail.allowed,
    refusal_category=guardrail.refusal.category.value if guardrail.refusal else None,
    refusal_code=guardrail.refusal.code.value if guardrail.refusal else None,
)
```

- [ ] **Step 2: Keep blocked and preview responses simple**

Blocked path:

```python
return _build_refused_response(..., trace_id=trace_id)
```

Preview path:

```python
return _build_preview_response(request, trace_id=trace_id)
```

Allowed path:
- let the runtime return its `trace_id`
- do not keep a second custom request-trace context abstraction in service

- [ ] **Step 3: Update integration tests to the simpler contract**

Use small fake helpers instead of fake trace-context classes.

Example:

```python
monkeypatch.setattr(agent_service, "trace_guardrail_decision", lambda **_: "guardrail-trace-1")
```

And for allowed path:

```python
class FakeRuntime:
    def invoke(self, payload):
        return agent_service.AgentRuntimeOutput(
            summary="I can help you explore the job database safely.",
            warnings=[],
            trace_id="runtime-trace-1",
        )
```

- [ ] **Step 4: Run the integration tests**

Run:

```powershell
uv run python -m pytest tests/integration/test_agent_api.py -v
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/service.py tests/integration/test_agent_api.py
git commit -m "refactor: trace guardrail with simple langfuse helper"
```

---

### Task 5: Verify the End-to-End Tracing Contract

**Files:**
- No required code changes unless verification exposes one

- [ ] **Step 1: Run the focused suite**

Run:

```powershell
uv run python -m pytest tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py tests/unit/test_agent_api_routes.py tests/integration/test_agent_api.py -v
```

Expected:
- All tests PASS

- [ ] **Step 2: Run import sanity**

Run:

```powershell
uv run python -c "from src.internhunter.api.app import app; print(app.title)"
uv run python -c "from src.agents.tracing import build_langchain_tracing_config; print(build_langchain_tracing_config(user_id='u1', session_id='s1').keys())"
```

Expected:
- app imports successfully
- tracing config returns callback/metadata keys when configured

- [ ] **Step 3: Run one live manual smoke with FastAPI**

Start:

```powershell
uv run python -m uvicorn src.internhunter.api.app:app --reload
```

Send:

```json
{
  "question": "What can you do?",
  "session_id": "trace-smoke-1",
  "user_id": "user-smoke-1"
}
```

Verify in Langfuse:
- one trace exists for the LangChain run
- input shows the user question
- output shows the agent answer
- trace metadata includes `user_id` and `session_id`

Send blocked request:

```json
{
  "question": "Drop the clean_jobs table."
}
```

Verify:
- one guardrail observation exists
- response still returns a `trace_id`

- [ ] **Step 4: If live Langfuse data is missing, capture the exact missing layer**

Check only these:
- callback handler not attached
- metadata not propagating
- guardrail helper not emitting observation
- local fallback trace id returned instead of active Langfuse trace id

Do not widen the tracing design during this verification pass.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "test: verify simplified langfuse tracing flow"
```

---

### Task 6: Sync Live Docs to the Simpler Tracing Model

**Files:**
- Modify: `docs/getting-started/setup.md`
- Modify: `docs/current-system/current_behavior.md`
- Modify: `docs/operations/monitoring.md`

- [ ] **Step 1: Update setup docs with the simpler model**

Document that:
- Langfuse tracing for the agent uses the official LangChain `CallbackHandler`
- `user_id` and `session_id` are attached through LangChain metadata
- the guardrail is traced separately because it runs outside LangChain

Suggested wording:

```md
Agent tracing uses Langfuse’s official LangChain callback integration for runtime calls. The pre-agent guardrail is traced separately as one Langfuse observation because it runs outside LangChain. If Langfuse is unavailable, the API still works and falls back to a local `trace_id`.
```

- [ ] **Step 2: Keep current behavior docs precise**

In `docs/current-system/current_behavior.md`, describe:
- runtime tracing via LangChain callback
- guardrail observation
- fail-open fallback

Do not imply:
- a large custom request-tracing framework
- tracing of every internal helper

- [ ] **Step 3: Update monitoring docs**

Keep the monitoring note minimal:
- Langfuse config comes from `.env`
- `/agent/ask` traces LangChain runtime and guardrail

- [ ] **Step 4: Run a docs consistency grep**

Run:

```powershell
rg -n "Langfuse|CallbackHandler|guardrail|trace_id|request-scoped trace" README.md docs
```

Expected:
- no stale wording about the old tracing framework
- docs reflect the simple callback-based setup plus guardrail observation

- [ ] **Step 5: Commit**

```bash
git add docs/getting-started/setup.md docs/current-system/current_behavior.md docs/operations/monitoring.md
git commit -m "docs: describe simplified langfuse tracing setup"
```

---

## Self-Review

### Spec coverage
- keeps tracing in `src/agents/`
- does not create `src/internhunter/observability/tracing.py`
- uses the official simple Langfuse + LangChain callback path
- supports `user_id`
- supports `session_id`
- captures question and answer through LangChain tracing
- keeps guardrail tracing
- preserves fail-open behavior

### Placeholder scan
- no TBD/TODO placeholders
- all tasks include exact file paths
- all test steps include commands
- implementation steps contain concrete code targets

### Type consistency
- runtime uses `build_langchain_tracing_config(...)`
- service uses `trace_guardrail_decision(...)`
- runtime output continues to return `trace_id`
- no custom request-trace context types remain in the target design

