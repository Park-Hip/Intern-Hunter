# Agent Layer Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify the database-agent layer down to the smallest readable MVP that can safely grow into question -> validated SQL -> execution, while preserving intentional boundaries such as the provider wrapper and SQL safety rules.

**Architecture:** Keep one thin route, one direct service flow, one intentional provider wrapper, and one explicit SQL safety/execution boundary. Remove duplicated request/runtime artifacts, reduce tracing/memory complexity, narrow the guardrail to true safety and scope, and align docs/tests with the simplified live behavior before building the real SQL path.

**Tech Stack:** FastAPI, Pydantic, LangChain/Ollama, pytest, existing InternHunter settings/docs structure

---

## File Structure

- Keep: `src/internhunter/api/routes/agent_routes.py`
- Modify: `src/internhunter/api/schemas/agent.py`
  - Shrink the HTTP contract to the smallest truthful live shape while preserving room for the later SQL path.
- Keep: `src/agents/provider.py`
  - Preserve this wrapper as an intentional boundary.
- Modify: `src/agents/service.py`
  - Collapse branching and remove extra orchestration/state seams not needed for MVP.
- Modify: `src/agents/runtime.py`
  - Keep the runtime wrapper small and align it with the simplified tracing/memory story.
- Modify: `src/agents/guardrail.py`
  - Keep safety and scope enforcement; remove proto-routing behavior that belongs later.
- Modify or Remove: `src/agents/memory.py`
  - Either delete it or reduce it to the smallest justified session helper, depending on the chosen MVP follow-up scope.
- Modify: `src/agents/tracing.py`
  - Reduce to one minimal tracing story that the code and tests agree on.
- Modify: `src/agents/types.py`
  - Remove or reduce internal artifacts that are not yet serving live behavior.
- Modify: `src/agents/state.py`
  - Remove if it is only duplicating request/runtime fields already represented elsewhere.
- Modify: `src/agents/prompts.py`
  - Make it the single source of truth for the runtime prompt or delegate cleanly to YAML.
- Modify: `src/config/prompts.yaml`
  - Keep prompt definitions aligned with whichever prompt source is retained.
- Modify: `tests/unit/test_agent_contract_models.py`
- Modify: `tests/unit/test_agent_runtime.py`
- Modify: `tests/unit/test_agent_api_routes.py`
- Modify: `tests/unit/test_agent_tracing.py`
- Modify: `tests/integration/test_agent_api.py`
- Modify: `README.md`
- Modify: `docs/api/overview.md`
- Modify: `docs/current-system/current_behavior.md`
- Modify: `docs/agent/architecture.md`
- Modify: `docs/agent/api_contract.md`
  - Update planning docs only where they currently misrepresent live complexity or scope.

### Task 1: Lock The Simplification Boundary In Tests

**Files:**
- Modify: `tests/unit/test_agent_contract_models.py`
- Modify: `tests/unit/test_agent_runtime.py`
- Modify: `tests/unit/test_agent_api_routes.py`
- Modify: `tests/unit/test_agent_tracing.py`
- Modify: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write the failing test updates that reflect the simplified architecture**

Update the tests so they assert the intended smaller surface:

- provider wrapper stays
- no duplicate internal request/runtime DTO chain is required
- tracing API has one agreed minimal interface
- route/service behavior still supports refusal, preview, and allowed-runtime responses
- tests stop expecting richer tracing lifecycle objects if those are being removed

Concrete test targets to introduce or adjust:

```python
def test_agent_module_keeps_provider_wrapper_but_drops_unused_internal_exports():
    import src.agents as agent_module

    assert hasattr(agent_module, "build_agent_runtime")
    assert not hasattr(agent_module, "SqlCandidateArtifact")
    assert not hasattr(agent_module, "ValidatedSqlArtifact")


def test_agent_runtime_returns_summary_with_minimal_trace_id():
    runtime = AgentRuntime(agent=fake_graph, memory=None)

    result = runtime.invoke(AgentRuntimeInput(question="Hello"))

    assert result.summary == "I can help you explore the job database safely."
    assert isinstance(result.trace_id, str)
    assert result.trace_id


def test_agent_api_preview_branch_keeps_execution_skipped_true():
    response = client.post("/agent/ask", json={"question": "Preview jobs by city.", "preview_only": True})

    assert response.status_code == 200
    assert response.json()["metadata"]["execution_skipped"] is True
```

- [ ] **Step 2: Run the targeted agent tests to capture the current failures**

Run:

```powershell
uv run pytest tests/unit/test_agent_contract_models.py tests/unit/test_agent_runtime.py tests/unit/test_agent_api_routes.py tests/unit/test_agent_tracing.py tests/integration/test_agent_api.py -q
```

Expected:

- failures or collection errors that describe the current overbuilt or inconsistent seams
- especially around tracing API mismatch and contract expectations

- [ ] **Step 3: Tighten assertions to the smallest stable public behavior**

Update the tests so they stop over-specifying future-facing behavior such as:

- rich tracing lifecycle internals
- unused internal artifacts
- response structures that imply live SQL/chart behavior

Representative direction:

```python
def test_allowed_request_returns_minimal_ok_envelope(monkeypatch):
    class FakeRuntime:
        def invoke(self, payload):
            return AgentRuntimeOutput(
                summary="I can help you explore the job database safely.",
                warnings=[],
                trace_id="trace-minimal-1",
            )

    monkeypatch.setattr(agent_service, "build_agent_runtime", lambda: FakeRuntime())

    response = client.post("/agent/ask", json={"question": "hello"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"] == "I can help you explore the job database safely."
```

- [ ] **Step 4: Run the focused tests again and verify the failures now point only at implementation gaps**

Run:

```powershell
uv run pytest tests/unit/test_agent_contract_models.py tests/unit/test_agent_runtime.py tests/unit/test_agent_api_routes.py tests/unit/test_agent_tracing.py tests/integration/test_agent_api.py -q
```

Expected:

- failures should now point at code that still needs simplification, not at outdated test assumptions

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_agent_contract_models.py tests/unit/test_agent_runtime.py tests/unit/test_agent_api_routes.py tests/unit/test_agent_tracing.py tests/integration/test_agent_api.py
git commit -m "test: lock simplified agent layer expectations"
```

### Task 2: Collapse Redundant Internal Models

**Files:**
- Modify: `src/agents/types.py`
- Modify: `src/agents/state.py`
- Modify: `src/internhunter/api/schemas/agent.py`
- Test: `tests/unit/test_agent_contract_models.py`

- [ ] **Step 1: Write the failing model-contract tests for the reduced object graph**

Add tests that express the new intended shape:

- one HTTP request model
- one minimal runtime input/output model if still justified
- no extra future-facing artifacts unless already used by live behavior

```python
def test_agent_request_model_is_the_single_live_request_shape():
    request = AgentAskRequest(question=" Count jobs by city. ", session_id=" s1 ")

    assert request.question == "Count jobs by city."
    assert request.session_id == "s1"


def test_preview_and_refusal_responses_allow_optional_sql_fields_without_future_artifacts():
    response = AgentAskPreviewResponse(
        question="Preview jobs by city.",
        summary="Preview only.",
        metadata=AgentResponseMetadata(trace_id="trace-1", execution_skipped=True),
    )

    assert response.status == "ok"
```

- [ ] **Step 2: Run the focused contract test to verify the current model graph is still too large**

Run:

```powershell
uv run pytest tests/unit/test_agent_contract_models.py -q
```

Expected:

- failures showing the current models still require or expose unnecessary internal artifacts

- [ ] **Step 3: Simplify the models**

Implementation direction:

- remove unused artifacts from `src/agents/types.py`
- remove `src/agents/state.py` entirely if it only mirrors request/response fields
- keep `src/internhunter/api/schemas/agent.py` as the main public contract
- retain only the smallest runtime result model if it genuinely helps decouple the service from the runtime

Representative reduced code target:

```python
class AgentRuntimeOutput(BaseModel):
    summary: str
    warnings: list[str] = Field(default_factory=list)
    trace_id: str


class AgentAskRequest(BaseModel):
    question: str
    session_id: str | None = None
    user_id: str | None = None
    preview_only: bool = False
```

- [ ] **Step 4: Run the contract and route tests to confirm the smaller model surface still works**

Run:

```powershell
uv run pytest tests/unit/test_agent_contract_models.py tests/unit/test_agent_api_routes.py -q
```

Expected:

- tests pass with a smaller, more direct model surface

- [ ] **Step 5: Commit**

```bash
git add src/agents/types.py src/agents/state.py src/internhunter/api/schemas/agent.py tests/unit/test_agent_contract_models.py tests/unit/test_agent_api_routes.py
git commit -m "refactor: collapse redundant agent models"
```

### Task 3: Simplify Tracing To One Minimal Story

**Files:**
- Modify: `src/agents/tracing.py`
- Modify: `src/agents/runtime.py`
- Modify: `src/agents/service.py`
- Test: `tests/unit/test_agent_tracing.py`
- Test: `tests/unit/test_agent_runtime.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write the failing tracing tests for the minimal target**

Target behavior:

- one helper to produce a trace id every request
- optional Langfuse callback wiring if configured
- no complex request-scoped trace context object unless it is still strictly necessary

```python
def test_build_local_trace_id_returns_non_empty_id():
    trace_id = build_local_trace_id()

    assert isinstance(trace_id, str)
    assert trace_id.startswith("agent-trace-")


def test_build_langchain_tracing_config_returns_empty_when_unconfigured():
    assert build_langchain_tracing_config(user_id=None, session_id=None) == {}
```

- [ ] **Step 2: Run the tracing-focused tests and confirm the current mismatch**

Run:

```powershell
uv run pytest tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py tests/integration/test_agent_api.py -q
```

Expected:

- failures showing disagreement between class-based trace-context expectations and the simplified function-based implementation

- [ ] **Step 3: Rewrite the implementation around one agreed minimal API**

Implementation direction:

- `service.py` generates or records one `trace_id`
- `runtime.py` asks tracing for optional callback config and final trace id
- `tracing.py` owns only:
  - local trace id creation
  - optional LangChain callback config
  - optional guardrail observation helper if kept

Representative target shape:

```python
def build_local_trace_id() -> str:
    return f"agent-trace-{uuid4()}"


def build_langchain_tracing_config(*, user_id: str | None, session_id: str | None) -> dict[str, Any]:
    ...


def trace_guardrail_decision(...) -> str:
    ...
```

- [ ] **Step 4: Run the tracing and API tests again**

Run:

```powershell
uv run pytest tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py tests/integration/test_agent_api.py -q
```

Expected:

- tracing tests pass
- route/runtime tests no longer depend on removed tracer classes

- [ ] **Step 5: Commit**

```bash
git add src/agents/tracing.py src/agents/runtime.py src/agents/service.py tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py tests/integration/test_agent_api.py
git commit -m "refactor: simplify agent tracing flow"
```

### Task 4: Keep The Provider Wrapper And Shrink The Runtime Around It

**Files:**
- Modify: `src/agents/runtime.py`
- Keep: `src/agents/provider.py`
- Modify: `src/agents/prompts.py`
- Modify: `src/config/prompts.yaml`
- Test: `tests/unit/test_agent_runtime.py`

- [ ] **Step 1: Write the failing runtime tests for the intended preserved boundary**

Add or adjust tests to assert:

- `AgentProvider` remains the intentional model-construction boundary
- runtime stays small and readable
- prompt source is unambiguous

```python
def test_build_agent_runtime_uses_agent_provider_wrapper():
    provider = _FakeProvider()

    runtime = build_agent_runtime(provider=provider, agent_factory=fake_factory)

    assert runtime is not None


def test_runtime_uses_single_prompt_source():
    assert build_agent_system_prompt().strip()
```

- [ ] **Step 2: Run the runtime tests**

Run:

```powershell
uv run pytest tests/unit/test_agent_runtime.py -q
```

Expected:

- failures if runtime still mixes too many seams or if prompt ownership is unclear

- [ ] **Step 3: Simplify runtime while preserving `src/agents/provider.py`**

Implementation direction:

- keep `AgentProvider`
- keep runtime construction simple
- remove extra indirection that is not helping readability
- choose one prompt source:
  - either `src/agents/prompts.py` owns the prompt
  - or `src/agents/prompts.py` cleanly loads from `settings.get_prompt(...)`

Representative target:

```python
def build_agent_runtime(provider: AgentProvider | None = None, agent_factory: Any | None = None) -> AgentRuntime:
    model_provider = provider or AgentProvider()
    model = model_provider.build_model()
    builder = agent_factory or create_agent
    agent = builder(model=model, tools=[], system_prompt=build_agent_system_prompt())
    return AgentRuntime(agent=agent)
```

- [ ] **Step 4: Run the runtime tests again**

Run:

```powershell
uv run pytest tests/unit/test_agent_runtime.py -q
```

Expected:

- runtime tests pass
- provider wrapper remains intact

- [ ] **Step 5: Commit**

```bash
git add src/agents/runtime.py src/agents/provider.py src/agents/prompts.py src/config/prompts.yaml tests/unit/test_agent_runtime.py
git commit -m "refactor: shrink runtime around provider boundary"
```

### Task 5: Narrow Guardrail And Remove Proto-Routing Behavior

**Files:**
- Modify: `src/agents/guardrail.py`
- Modify: `src/agents/service.py`
- Test: `tests/unit/test_agent_api_routes.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write the failing tests for a narrower guardrail**

Target behavior:

- guardrail blocks destructive requests
- guardrail blocks prompt injection
- guardrail blocks clearly out-of-scope requests
- guardrail does not own future resume routing or chart-routing logic

```python
def test_guardrail_refuses_destructive_request():
    response = client.post("/agent/ask", json={"question": "Drop the clean_jobs table."})

    assert response.status_code == 200
    assert response.json()["status"] == "refused"


def test_guardrail_refuses_unrelated_topic():
    response = client.post("/agent/ask", json={"question": "Who won the last World Cup?"})

    assert response.json()["error"]["category"] == "out_of_scope"
```

- [ ] **Step 2: Run the route and integration tests**

Run:

```powershell
uv run pytest tests/unit/test_agent_api_routes.py tests/integration/test_agent_api.py -q
```

Expected:

- failures if service logic still depends on the guardrail as a proto-router

- [ ] **Step 3: Simplify the guardrail and service boundary**

Implementation direction:

- keep deterministic safety checks
- reduce allowlists that pretend the system already has resume/chart tool routing
- let the allowed path stay generic until real SQL and real non-SQL tools exist

Representative direction:

```python
if _matches_any(normalized, PROMPT_INJECTION_PATTERNS):
    return blocked_prompt_injection

if _matches_any(normalized, DESTRUCTIVE_SQL_PATTERNS):
    return blocked_destructive_request

if _matches_any(normalized, JOB_SCOPE_PATTERNS) or _matches_any(normalized, SMALL_TALK_PATTERNS):
    return GuardrailDecision(allowed=True)

return blocked_out_of_scope
```

- [ ] **Step 4: Run the route and integration tests again**

Run:

```powershell
uv run pytest tests/unit/test_agent_api_routes.py tests/integration/test_agent_api.py -q
```

Expected:

- tests pass with a smaller guardrail role

- [ ] **Step 5: Commit**

```bash
git add src/agents/guardrail.py src/agents/service.py tests/unit/test_agent_api_routes.py tests/integration/test_agent_api.py
git commit -m "refactor: narrow agent guardrail responsibilities"
```

### Task 6: Remove Or Minimize Session Memory

**Files:**
- Modify or Delete: `src/agents/memory.py`
- Modify: `src/agents/runtime.py`
- Modify: `src/agents/service.py`
- Test: `tests/unit/test_agent_runtime.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write the failing tests for the chosen memory scope**

Choose one of two paths before implementation:

- no session memory in the simplified MVP foundation
- tiny in-process message history only, with no LangGraph-style config abstraction

Test one explicitly. Example for removal:

```python
def test_agent_runtime_invokes_graph_without_memory_config_when_memory_is_disabled():
    runtime = AgentRuntime(agent=fake_graph)

    runtime.invoke(AgentRuntimeInput(question="Hello"))

    assert fake_graph.calls == [({"messages": [{"role": "user", "content": "Hello"}]}, None)]
```

- [ ] **Step 2: Run the runtime and integration tests**

Run:

```powershell
uv run pytest tests/unit/test_agent_runtime.py tests/integration/test_agent_api.py -q
```

Expected:

- failures showing the current memory abstraction still shapes runtime behavior

- [ ] **Step 3: Simplify or remove the memory seam**

Implementation direction:

- if memory is removed, delete `src/agents/memory.py` and runtime caching
- if memory is kept, reduce it to direct append/get logic and remove `build_invocation_config()`

Representative reduced target:

```python
class AgentMemoryStore:
    def __init__(self, limit: int = 6) -> None:
        self.limit = limit
        self._messages: dict[str, list[dict[str, str]]] = defaultdict(list)

    def append(self, session_id: str, role: str, content: str) -> None:
        ...

    def get(self, session_id: str) -> list[dict[str, str]]:
        ...
```

- [ ] **Step 4: Run the runtime and integration tests again**

Run:

```powershell
uv run pytest tests/unit/test_agent_runtime.py tests/integration/test_agent_api.py -q
```

Expected:

- session behavior is either intentionally absent or intentionally tiny and understandable

- [ ] **Step 5: Commit**

```bash
git add src/agents/memory.py src/agents/runtime.py src/agents/service.py tests/unit/test_agent_runtime.py tests/integration/test_agent_api.py
git commit -m "refactor: reduce agent session memory complexity"
```

### Task 7: Reduce The Public Contract To Truthful MVP Behavior And Sync Docs

**Files:**
- Modify: `src/internhunter/api/schemas/agent.py`
- Modify: `README.md`
- Modify: `docs/api/overview.md`
- Modify: `docs/current-system/current_behavior.md`
- Modify: `docs/agent/architecture.md`
- Modify: `docs/agent/api_contract.md`
- Test: `tests/unit/test_agent_contract_models.py`
- Test: `tests/unit/test_agent_api_routes.py`

- [ ] **Step 1: Write the failing tests for the reduced public contract**

Target behavior:

- docs and tests describe the current scaffold honestly
- no doc or test implies live SQL execution, live chart generation, or live resume-tool routing

Representative checks:

```python
def test_ok_response_allows_summary_only_runtime_shape():
    response = AgentAskOkResponse(
        question="What can you do?",
        summary="I can help you explore the job database safely.",
        metadata=AgentResponseMetadata(trace_id="trace-1", execution_skipped=True),
    )

    assert response.sql.executed_sql is None
```

- [ ] **Step 2: Run the focused contract and route tests**

Run:

```powershell
uv run pytest tests/unit/test_agent_contract_models.py tests/unit/test_agent_api_routes.py -q
```

Expected:

- failures if contract code still overstates live functionality

- [ ] **Step 3: Update the public contract and docs**

Implementation direction:

- keep the endpoint and minimal envelope
- clearly separate:
  - current live behavior
  - future SQL execution target
- remove or downplay large-system phrasing that implies already-live tool orchestration

Docs to update:

- `README.md`
- `docs/api/overview.md`
- `docs/current-system/current_behavior.md`
- `docs/agent/architecture.md`
- `docs/agent/api_contract.md`

Required doc stance:

- current live behavior is refusal + preview stub + runtime-backed summary path
- provider wrapper is intentional
- SQL generation/validation/execution is the next core milestone
- charting, resume routing, persistent memory, and richer tracing are deferred

- [ ] **Step 4: Run the focused tests and a targeted docs consistency sweep**

Run:

```powershell
uv run pytest tests/unit/test_agent_contract_models.py tests/unit/test_agent_api_routes.py -q
rg -n "/agent/ask|preview_only|trace_id|runtime-backed|SQL generation|chart|resume" README.md docs/api/overview.md docs/current-system/current_behavior.md docs/agent/architecture.md docs/agent/api_contract.md
```

Expected:

- tests pass
- docs no longer describe a larger live system than the code supports

- [ ] **Step 5: Commit**

```bash
git add src/internhunter/api/schemas/agent.py README.md docs/api/overview.md docs/current-system/current_behavior.md docs/agent/architecture.md docs/agent/api_contract.md tests/unit/test_agent_contract_models.py tests/unit/test_agent_api_routes.py
git commit -m "docs: align agent contract with simplified mvp scope"
```

### Task 8: Final Verification Of The Simplified Agent Foundation

**Files:**
- Verify: `src/agents/service.py`
- Verify: `src/agents/runtime.py`
- Verify: `src/agents/provider.py`
- Verify: `src/agents/guardrail.py`
- Verify: `src/agents/tracing.py`
- Verify: `src/internhunter/api/schemas/agent.py`
- Verify: `README.md`
- Verify: `docs/api/overview.md`
- Verify: `docs/current-system/current_behavior.md`

- [ ] **Step 1: Run the focused agent test suite**

Run:

```powershell
uv run pytest tests/unit/test_agent_contract_models.py tests/unit/test_agent_runtime.py tests/unit/test_agent_api_routes.py tests/unit/test_agent_tracing.py tests/integration/test_agent_api.py -q
```

Expected:

- all focused agent tests pass

- [ ] **Step 2: Run one small import/runtime smoke**

Run:

```powershell
uv run python -c "from src.agents.runtime import build_agent_runtime; print(type(build_agent_runtime()).__name__)"
```

Expected:

- prints `AgentRuntime` without crashing on import-time wiring

- [ ] **Step 3: Run the targeted docs consistency search**

Run:

```powershell
rg -n "Langfuse v3 trace context|bounded ReAct Runtime|resume-tool routing|chart generation|persistent session follow-up context" README.md docs/api/overview.md docs/current-system/current_behavior.md docs/agent
```

Expected:

- any remaining mentions are clearly labeled as future or planning-only

- [ ] **Step 4: Review the simplified foundation against the MVP goal**

Checklist:

- provider wrapper preserved intentionally
- service flow is direct and readable
- tracing is no longer a destabilizing abstraction
- memory is either gone or tiny
- docs describe the real code, not the aspirational system
- the codebase is now ready for the real next milestone: safe SQL preview and validation

- [ ] **Step 5: Commit**

```bash
git add src/agents src/internhunter/api/schemas/agent.py README.md docs/api/overview.md docs/current-system/current_behavior.md docs/agent
git commit -m "refactor: simplify agent foundation for sql mvp"
```

## Self-Review

### Spec coverage

This plan covers the requested simplification themes:

- DTO reduction
- layer merging
- tracing simplification
- memory simplification
- guardrail narrowing
- live docs sync
- preserving `src/agents/provider.py` as an intentional boundary

It does not implement SQL execution itself; it prepares the codebase for that next milestone, which matches the request.

### Placeholder scan

No `TBD`, `TODO`, or “implement later” placeholders are used in the execution steps. Each task names exact files, concrete tests, exact commands, and expected outcomes.

### Type consistency

The plan consistently treats:

- `AgentAskRequest` as the public request model
- `AgentRuntimeOutput` as the minimal runtime result model if still retained
- `AgentProvider` as preserved
- SQL execution work as deferred until after simplification

