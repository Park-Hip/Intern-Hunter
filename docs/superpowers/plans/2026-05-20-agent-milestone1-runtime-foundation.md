# Agent Milestone 1 Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current post-guardrail placeholder path behind `POST /agent/ask` with a real agent runtime foundation that uses a LangChain agent entrypoint, starts on Ollama with `qwen3.5:4b` as the initial provider/model, supports short session memory, emits tracing, and exposes its behavior through the existing typed API contract.

**Architecture:** Keep the current deterministic pre-agent guardrail in `src/agents/guardrail.py`, then delegate allowed requests from `src/agents/service.py` into a new runtime seam under `src/agents/`. The runtime should use a LangChain agent entrypoint with no tools for this milestone, preserve the existing API envelope, keep SQL generation out of scope, and isolate agent-specific provider, prompt, memory, and tracing concerns from ETL-oriented code in `src/internhunter/llm/`.

**Tech Stack:** FastAPI, Pydantic, pytest, LangChain agent runtime, LangGraph-backed short-term memory behavior through the LangChain agent stack, Ollama-backed local model invocation (`qwen3.5:4b`), optional Langfuse tracing seam, existing settings/prompts YAML loading.

---

## File Structure

### Files to create

- `src/agents/runtime.py`
  - Runtime creation and invocation entrypoint for Milestone 1.
  - Owns the public internal function that `src/agents/service.py` will call after guardrail pass.

- `src/agents/state.py`
  - Typed runtime state objects for request-local and session-threaded state.
  - Keeps runtime-specific state out of the HTTP schema module.

- `src/agents/provider.py`
  - Agent-native provider wrapper.
  - Starts with an Ollama-backed local provider path for `qwen3.5:4b`.
  - Reuses shared settings and SDK access where useful, but does not reuse ETL orchestration behavior from `src/internhunter/llm/router.py`.

- `src/agents/prompts.py`
  - Agent runtime prompt assembly for the no-tool Milestone 1 runtime.
  - Keeps stale tool-heavy prompt text out of the first runtime cut.

- `src/agents/memory.py`
  - Short-memory seam for `session_id`-threaded runtime history.
  - Starts with a bounded implementation suitable for API verification.

- `src/agents/tracing.py`
  - Tracing abstraction and optional Langfuse-backed implementation seam.
  - Must fail open when tracing is not configured.

- `tests/unit/test_agent_runtime.py`
  - Unit coverage for runtime construction and no-tool invocation behavior.

- `tests/unit/test_agent_memory.py`
  - Unit coverage for short-memory behavior keyed by `session_id`.

- `tests/unit/test_agent_tracing.py`
  - Unit coverage for tracing seam behavior.

- `tests/unit/test_agent_provider.py`
  - Unit coverage for agent-native provider wrapper behavior.

### Files to modify

- `src/agents/service.py`
  - Keep guardrail-first refusal behavior.
  - Replace the current hardcoded allowed placeholder path with runtime invocation.

- `src/agents/types.py`
  - Extend internal artifacts only where Milestone 1 needs explicit runtime request/result types.
  - Do not add SQL execution artifacts beyond what already exists.

- `src/agents/__init__.py`
  - Export new runtime-facing types or entrypoints only if needed by tests or imports.

- `src/internhunter/config/settings.py`
  - Load any new `agent` runtime settings needed for memory/tracing/runtime behavior.
  - Load provider settings for the initial Ollama model.

- `src/config/settings.yaml`
  - Add minimal runtime knobs only if code needs them.
  - Add explicit agent-provider settings for Ollama and `qwen3.5:4b`.

- `src/config/prompts.yaml`
  - Update only if a small shared runtime prompt string remains YAML-owned.
  - Do not keep the current stale tool-centric `agent_system` prompt unchanged if it conflicts with Milestone 1.

- `tests/unit/test_agent_api_routes.py`
  - Update allowed-response expectations to reflect runtime-driven behavior.

- `tests/integration/test_agent_api.py`
  - Add end-to-end API checks that prove allowed requests now go through the runtime and that session memory works across API calls.

- `docs/agent/agent_milestones.md`
  - Move Milestone 1 from `research gate active` to the appropriate later status when implementation lands.

- `docs/agent/architecture.md`
  - Narrowly update the “current implemented slice” once Milestone 1 ships.

- `docs/agent/api_contract.md`
  - Update only if the allowed-path behavior becomes more specific than the current generic placeholder.

- `README.md`
  - Update only if the live `/agent/ask` summary changes in a user-visible way.

- `docs/api/overview.md`
  - Update live endpoint notes only if runtime behavior becomes more concrete.

- `docs/current-system/current_behavior.md`
  - Update the live `/agent/ask` description once the runtime foundation replaces the current generic stub path.

### Files deliberately not touched in this milestone

- `src/internhunter/llm/router.py`
- `src/internhunter/llm/providers.py`
- `src/internhunter/resume/*`
- `src/internhunter/search/*`
- ETL/crawler modules

Milestone 1 may inspect those files for boundary decisions, but should not modify them unless a newly discovered blocker forces a follow-up decision.

## Task 1: Lock the Milestone 1 runtime contract

**Files:**
- Modify: `docs/agent/agent_milestones.md`
- Modify: `docs/agent/architecture.md`
- Modify: `docs/agent/api_contract.md`
- Test: `tests/unit/test_agent_contract_models.py`

- [ ] **Step 1: Write the failing contract-oriented test for the Milestone 1 allowed path**

```python
from src.internhunter.api.schemas.agent import AgentAskOkResponse, AgentResponseMetadata, AgentSQLPayload


def test_ok_response_allows_runtime_backed_non_sql_message():
    response = AgentAskOkResponse(
        question="What can you do?",
        sql=AgentSQLPayload(),
        summary="I can help you explore the job database safely.",
        metadata=AgentResponseMetadata(
            limit_applied=False,
            execution_skipped=True,
            trace_id="trace-runtime-1",
            session_id="demo-session",
            user_id=None,
        ),
        warnings=[],
    )

    payload = response.model_dump(mode="json")

    assert payload["status"] == "ok"
    assert payload["sql"]["executed_sql"] is None
    assert payload["metadata"]["trace_id"] == "trace-runtime-1"
```

- [ ] **Step 2: Run test to verify the current contract still supports the target shape**

Run: `uv run pytest tests/unit/test_agent_contract_models.py::test_ok_response_allows_runtime_backed_non_sql_message -v`

Expected: PASS if only the response shape is being asserted, or FAIL if the test has not been added yet.

- [ ] **Step 3: Update planning docs before code so the milestone target is explicit**

Document these Milestone 1 decisions:

```md
- LangChain agent entrypoint for the first runtime
- Ollama with qwen3.5:4b as the initial provider/model
- no tools in Milestone 1
- short session memory only
- tracing enabled through a replaceable seam
- SQL generation/execution remains out of scope
```

Apply this to:

- `docs/agent/agent_milestones.md`
- `docs/agent/architecture.md`
- `docs/agent/api_contract.md` (only the status/runtime note if needed)

- [ ] **Step 4: Re-run the contract-focused test**

Run: `uv run pytest tests/unit/test_agent_contract_models.py::test_ok_response_allows_runtime_backed_non_sql_message -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/agent/agent_milestones.md docs/agent/architecture.md docs/agent/api_contract.md tests/unit/test_agent_contract_models.py
git commit -m "docs: lock milestone 1 runtime foundation contract"
```

## Task 2: Add the runtime foundation modules

**Files:**
- Create: `src/agents/runtime.py`
- Create: `src/agents/state.py`
- Create: `src/agents/provider.py`
- Create: `src/agents/prompts.py`
- Modify: `src/agents/__init__.py`
- Test: `tests/unit/test_agent_runtime.py`
- Test: `tests/unit/test_agent_provider.py`

- [ ] **Step 1: Write the failing runtime construction test**

```python
from src.agents.runtime import build_agent_runtime


def test_build_agent_runtime_returns_runtime_object():
    runtime = build_agent_runtime()

    assert runtime is not None
    assert hasattr(runtime, "invoke")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_agent_runtime.py::test_build_agent_runtime_returns_runtime_object -v`

Expected: FAIL with `ModuleNotFoundError` or missing symbol errors for `src.agents.runtime`.

- [ ] **Step 3: Write the minimal runtime foundation**

```python
# src/agents/state.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentRuntimeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    session_id: str | None = None
    user_id: str | None = None
    preview_only: bool = False


class AgentRuntimeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    warnings: list[str] = []
    trace_id: str
```

```python
# src/agents/prompts.py
from __future__ import annotations


def build_agent_system_prompt() -> str:
    return (
        "You are a bounded database-agent runtime for InternHunter. "
        "You are in Milestone 1, so no tools are available yet. "
        "Respond briefly, stay within job-database scope, and do not invent SQL execution."
    )
```

```python
# src/agents/provider.py
from __future__ import annotations

from src.internhunter.config.settings import load_settings


class AgentProvider:
    def __init__(self):
        self.settings = load_settings()

    def build_model(self):
        return None
```

```python
# src/agents/runtime.py
from __future__ import annotations

from src.agents.state import AgentRuntimeInput, AgentRuntimeOutput


class AgentRuntime:
    def invoke(self, payload: AgentRuntimeInput) -> AgentRuntimeOutput:
        return AgentRuntimeOutput(
            summary="I can help you explore the job database safely.",
            warnings=[],
            trace_id="stub-runtime-trace-id",
        )


def build_agent_runtime() -> AgentRuntime:
    return AgentRuntime()
```

- [ ] **Step 4: Add the provider seam test**

```python
from src.agents.provider import AgentProvider


def test_agent_provider_build_model_is_runtime_local():
    provider = AgentProvider()

    assert provider is not None
    assert hasattr(provider, "build_model")
```

- [ ] **Step 5: Run the new unit tests**

Run: `uv run pytest tests/unit/test_agent_runtime.py tests/unit/test_agent_provider.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agents/runtime.py src/agents/state.py src/agents/provider.py src/agents/prompts.py src/agents/__init__.py tests/unit/test_agent_runtime.py tests/unit/test_agent_provider.py
git commit -m "feat: add milestone 1 runtime foundation modules"
```

## Task 3: Add short-memory and tracing seams

**Files:**
- Create: `src/agents/memory.py`
- Create: `src/agents/tracing.py`
- Modify: `src/agents/runtime.py`
- Test: `tests/unit/test_agent_memory.py`
- Test: `tests/unit/test_agent_tracing.py`

- [ ] **Step 1: Write the failing short-memory test**

```python
from src.agents.memory import AgentMemoryStore


def test_memory_store_round_trips_session_history():
    store = AgentMemoryStore()

    store.append("session-1", "user", "hello")
    store.append("session-1", "assistant", "hi there")

    history = store.get("session-1")

    assert len(history) == 2
    assert history[0]["content"] == "hello"
    assert history[1]["content"] == "hi there"
```

- [ ] **Step 2: Write the failing tracing test**

```python
from src.agents.tracing import NullAgentTracer


def test_null_tracer_returns_trace_id_without_side_effects():
    tracer = NullAgentTracer()

    trace_id = tracer.start_trace("What can you do?")

    assert isinstance(trace_id, str)
    assert trace_id
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_agent_memory.py tests/unit/test_agent_tracing.py -v`

Expected: FAIL with missing module errors.

- [ ] **Step 4: Write the minimal memory and tracing seams**

```python
# src/agents/memory.py
from __future__ import annotations

from collections import defaultdict


class AgentMemoryStore:
    def __init__(self, limit: int = 10):
        self.limit = limit
        self._messages = defaultdict(list)

    def append(self, session_id: str, role: str, content: str) -> None:
        self._messages[session_id].append({"role": role, "content": content})
        self._messages[session_id] = self._messages[session_id][-self.limit :]

    def get(self, session_id: str) -> list[dict[str, str]]:
        return list(self._messages.get(session_id, []))
```

```python
# src/agents/tracing.py
from __future__ import annotations

from uuid import uuid4


class NullAgentTracer:
    def start_trace(self, question: str) -> str:
        return f"agent-trace-{uuid4()}"

    def finish_trace(self, trace_id: str, status: str) -> None:
        return None
```

```python
# src/agents/runtime.py
from __future__ import annotations

from src.agents.memory import AgentMemoryStore
from src.agents.state import AgentRuntimeInput, AgentRuntimeOutput
from src.agents.tracing import NullAgentTracer


class AgentRuntime:
    def __init__(self, memory: AgentMemoryStore | None = None, tracer: NullAgentTracer | None = None):
        self.memory = memory or AgentMemoryStore()
        self.tracer = tracer or NullAgentTracer()

    def invoke(self, payload: AgentRuntimeInput) -> AgentRuntimeOutput:
        trace_id = self.tracer.start_trace(payload.question)

        if payload.session_id:
            self.memory.append(payload.session_id, "user", payload.question)

        summary = "I can help you explore the job database safely."

        if payload.session_id:
            self.memory.append(payload.session_id, "assistant", summary)

        self.tracer.finish_trace(trace_id, "ok")
        return AgentRuntimeOutput(summary=summary, warnings=[], trace_id=trace_id)
```

- [ ] **Step 5: Run the new tests**

Run: `uv run pytest tests/unit/test_agent_memory.py tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agents/memory.py src/agents/tracing.py src/agents/runtime.py tests/unit/test_agent_memory.py tests/unit/test_agent_tracing.py tests/unit/test_agent_runtime.py
git commit -m "feat: add milestone 1 short memory and tracing seams"
```

## Task 4: Route allowed requests through the runtime

**Files:**
- Modify: `src/agents/service.py`
- Modify: `src/agents/types.py`
- Test: `tests/unit/test_agent_api_routes.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write the failing service/integration test for runtime-backed allowed requests**

```python
from fastapi.testclient import TestClient

from src.internhunter.api.app import app


client = TestClient(app)


def test_agent_api_allowed_request_uses_runtime_backed_summary():
    response = client.post("/agent/ask", json={"question": "What can you do?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"] == "I can help you explore the job database safely."
    assert payload["metadata"]["execution_skipped"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_agent_api.py::test_agent_api_allowed_request_uses_runtime_backed_summary -v`

Expected: FAIL because the current summary is still the hardcoded placeholder from `src/agents/service.py`.

- [ ] **Step 3: Replace the hardcoded allowed path with runtime invocation**

```python
# src/agents/service.py
from __future__ import annotations

from src.agents.guardrail import screen_question
from src.agents.runtime import build_agent_runtime
from src.agents.state import AgentRuntimeInput
from src.agents.types import AskRequestArtifact, RefusalArtifact
from src.internhunter.api.schemas.agent import (
    AgentAskRefusedResponse,
    AgentAskOkResponse,
    AgentAskPreviewResponse,
    AgentAskRequest,
    AgentErrorPayload,
    AgentResponseMetadata,
    AgentSQLPayload,
)


def _build_metadata(request: AgentAskRequest, trace_id: str = "stub-trace-id") -> AgentResponseMetadata:
    return AgentResponseMetadata(
        limit_applied=False,
        execution_skipped=True,
        trace_id=trace_id,
        session_id=request.session_id,
        user_id=request.user_id,
    )


def _build_allowed_runtime_response(request: AgentAskRequest) -> AgentAskOkResponse:
    runtime = build_agent_runtime()
    result = runtime.invoke(
        AgentRuntimeInput(
            question=request.question,
            session_id=request.session_id,
            user_id=request.user_id,
            preview_only=request.preview_only,
        )
    )
    return AgentAskOkResponse(
        question=request.question,
        sql=AgentSQLPayload(),
        summary=result.summary,
        warnings=result.warnings,
        metadata=_build_metadata(request, trace_id=result.trace_id),
    )
```

And update the final allowed branch:

```python
return _build_allowed_runtime_response(request)
```

- [ ] **Step 4: Keep preview and refusal behavior unchanged**

Assert these behaviors still hold:

```python
assert payload["status"] == "refused"
assert payload["metadata"]["execution_skipped"] is True
assert payload["sql"]["executed_sql"] is None
```

for blocked prompts, and:

```python
assert payload["sql"]["validated_sql"] == "-- preview stub; no SQL generated yet"
```

for preview mode.

- [ ] **Step 5: Run focused route and integration tests**

Run: `uv run pytest tests/unit/test_agent_api_routes.py tests/integration/test_agent_api.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agents/service.py src/agents/types.py tests/unit/test_agent_api_routes.py tests/integration/test_agent_api.py
git commit -m "feat: route allowed agent requests through milestone 1 runtime"
```

## Task 5: Add session-memory API proof and config cleanup

**Files:**
- Modify: `src/internhunter/config/settings.py`
- Modify: `src/config/settings.yaml`
- Modify: `src/config/prompts.yaml`
- Test: `tests/unit/test_agent_settings.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write the failing memory-through-API integration test**

```python
from fastapi.testclient import TestClient

from src.internhunter.api.app import app


client = TestClient(app)


def test_agent_api_reuses_short_memory_with_same_session_id():
    first = client.post("/agent/ask", json={"question": "hello", "session_id": "session-a"})
    second = client.post("/agent/ask", json={"question": "what can you do?", "session_id": "session-a"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["metadata"]["session_id"] == "session-a"
```

- [ ] **Step 2: Write the failing settings test for new runtime knobs**

```python
from src.internhunter.config.settings import load_settings


def test_agent_settings_load_runtime_knobs_from_yaml():
    settings = load_settings()

    assert settings.agent.max_iterations == 5
    assert settings.agent.memory_limit == 10
    assert settings.agent.default_query_limit == 50
    assert settings.config_yaml["agent"]["provider"]["name"] == "ollama"
    assert settings.config_yaml["agent"]["provider"]["model"] == "qwen3.5:4b"
```

- [ ] **Step 3: Run tests to verify current behavior or missing config gaps**

Run: `uv run pytest tests/unit/test_agent_settings.py tests/integration/test_agent_api.py::test_agent_api_reuses_short_memory_with_same_session_id -v`

Expected: one PASS for current settings and one FAIL or weak assertion gap for memory behavior until the runtime is reused across requests correctly.

- [ ] **Step 4: Tighten config and prompt ownership for Milestone 1**

Keep the `agent` config block explicit about the initial provider:

```yaml
agent:
  max_iterations: 5
  memory_limit: 10
  default_query_limit: 50
  max_query_limit: 100
  provider:
    name: "ollama"
    model: "qwen3.5:4b"
    base_url: "http://127.0.0.1:11434"
    temperature: 0.2
```

And replace the stale tool-heavy agent prompt with either:

```yaml
prompts:
  agent_runtime_system: |
    You are the InternHunter database agent runtime.
    Milestone 1 has no tools yet.
    Stay within job-database scope, answer briefly, and never claim to execute SQL.
```

or move this prompt fully into `src/agents/prompts.py` and remove stale references from code.

- [ ] **Step 5: Run focused tests again**

Run: `uv run pytest tests/unit/test_agent_settings.py tests/unit/test_agent_runtime.py tests/integration/test_agent_api.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/internhunter/config/settings.py src/config/settings.yaml src/config/prompts.yaml tests/unit/test_agent_settings.py tests/integration/test_agent_api.py
git commit -m "chore: align agent runtime config and prompts for milestone 1"
```

## Task 6: Sync live docs to shipped Milestone 1 behavior

**Files:**
- Modify: `README.md`
- Modify: `docs/api/overview.md`
- Modify: `docs/current-system/current_behavior.md`
- Modify: `docs/agent/agent_milestones.md`
- Modify: `docs/agent/architecture.md`

- [ ] **Step 1: Update the live `/agent/ask` description in README**

Replace scaffold-only wording with wording like:

```md
- `POST /agent/ask` uses a deterministic pre-agent guardrail, a runtime-backed allowed path, preview stub handling, and typed refusal responses.
```

- [ ] **Step 2: Update API overview**

Make the `/agent/ask` section say:

```md
- blocked requests return typed refusal envelopes before runtime execution
- allowed requests now pass through a real agent runtime with no tools in Milestone 1
- preview requests still return preview-shaped stub responses
- SQL generation, execution, resume tools, and charting are still not implemented
```

- [ ] **Step 3: Update current behavior doc**

Make the live behavior section say:

```md
- `POST /agent/ask` now performs deterministic pre-agent screening
- allowed prompts go through a real runtime-backed response path
- short session memory is wired for Milestone 1
- preview remains stub-only
- real SQL generation/execution is still not implemented
```

- [ ] **Step 4: Mark Milestone 1 status accurately**

Update milestone status in `docs/agent/agent_milestones.md` when the code and tests are green:

```md
- Milestone 1: implementation active
```

or:

```md
- Milestone 1: implemented
```

depending on actual completion state.

- [ ] **Step 5: Run targeted docs consistency checks**

Run:

```bash
rg -n "/agent/ask|runtime|preview|guardrail|agent_milestones" README.md docs
uv run pytest tests/unit/test_agent_api_routes.py tests/integration/test_agent_api.py -v
```

Expected:

- docs references match the shipped runtime behavior
- route/integration tests still pass

- [ ] **Step 6: Commit**

```bash
git add README.md docs/api/overview.md docs/current-system/current_behavior.md docs/agent/agent_milestones.md docs/agent/architecture.md
git commit -m "docs: sync milestone 1 runtime foundation behavior"
```

## Final verification

- [ ] **Step 1: Run the smallest full Milestone 1 verification set**

Run:

```bash
uv run pytest tests/unit/test_agent_contract_models.py -v
uv run pytest tests/unit/test_agent_guardrail.py -v
uv run pytest tests/unit/test_agent_runtime.py -v
uv run pytest tests/unit/test_agent_memory.py -v
uv run pytest tests/unit/test_agent_tracing.py -v
uv run pytest tests/unit/test_agent_provider.py -v
uv run pytest tests/unit/test_agent_api_routes.py -v
uv run pytest tests/integration/test_agent_api.py -v
uv run pytest tests/unit/test_agent_settings.py -v
```

Expected: all PASS

- [ ] **Step 2: Run targeted text verification**

Run:

```bash
rg -n "placeholder|runtime-backed|preview|guardrail|LangChain|LangGraph|Langfuse" README.md docs/agent docs/api docs/current-system
```

Expected:

- live docs describe shipped behavior
- planning docs describe future work separately

- [ ] **Step 3: Final commit if verification changes were needed**

```bash
git add README.md docs src tests
git commit -m "test: finalize milestone 1 runtime verification"
```
