# Database Agent Phase 2 Route And Orchestration Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a first thin `POST /agent/ask` endpoint that accepts the Phase 1 request contract, delegates immediately to a minimal orchestration seam, and returns a stub shared envelope without implementing any real agent behavior.

**Architecture:** Keep the route layer extremely thin: a new FastAPI router module owns only HTTP mapping, request parsing, and response_model declaration. A new agent service module owns the placeholder orchestration entrypoint and returns deterministic Phase 1 response models, with no provider, SQL, routing, memory, or resume behavior yet.

**Tech Stack:** FastAPI, Pydantic v2, pytest, TestClient

---

## File Structure

**Create**
- `src/agents/service.py`
  - Minimal orchestration seam for Phase 2.
  - Exposes one function that accepts `AgentAskRequest` and returns a stub Phase 1 envelope.
- `src/internhunter/api/routes/agent_routes.py`
  - New `POST /agent/ask` route only.
  - Delegates to `src.agents.service`.
- `tests/unit/test_agent_api_routes.py`
  - Focused endpoint tests for existence, malformed payload handling, and stub happy-path behavior.

**Modify**
- `src/agents/__init__.py`
  - Re-export the new service entrypoint if helpful for a stable import path.
- `src/internhunter/api/app.py`
  - Include the new agent router without changing existing routes.
- `docs/agent/database_agent_wave1_implementation_plan.md`
  - Check off Phase 2 items only after tests pass.

**Keep Unchanged**
- `src/internhunter/api/routes/demo_routes.py`
- existing ETL, search, and resume code
- Phase 1 contract files unless a tiny import/export adjustment is required

## Implementation Notes Before Coding

- Use the existing Phase 1 models from `src/internhunter/api/schemas/agent.py` as-is.
- Keep the response stub deterministic and obviously non-final.
- Do not add any provider, SQL, guardrail, resume, chart, summary, or memory logic beyond returning typed placeholders.
- Keep the stub orchestration return shape small:
  - non-preview request -> `AgentAskOkResponse`
  - preview request -> `AgentAskPreviewResponse`
- Refused responses remain in the contract but do not need real runtime triggering in Phase 2.
- Return warnings that clearly state the response is a stub and no execution occurred.

### Suggested Stub Envelope Shape

For normal requests:

```python
AgentAskOkResponse(
    question=request.question,
    sql=AgentSQLPayload(),
    summary="Agent endpoint is wired. Real orchestration is not implemented yet.",
    warnings=["Stub response only. No SQL was generated or executed."],
    metadata=AgentResponseMetadata(
        limit_applied=False,
        execution_skipped=True,
        trace_id="stub-trace-id",
        session_id=request.session_id,
        user_id=request.user_id,
    ),
)
```

For preview requests:

```python
AgentAskPreviewResponse(
    question=request.question,
    sql=AgentSQLPayload(validated_sql="-- preview stub; no SQL generated yet"),
    summary="Preview mode is wired. Real SQL preview is not implemented yet.",
    warnings=["Stub preview only. No SQL was executed."],
    metadata=AgentResponseMetadata(
        limit_applied=False,
        execution_skipped=True,
        trace_id="stub-trace-id",
        session_id=request.session_id,
        user_id=request.user_id,
    ),
)
```

The exact trace ID value can be a fixed stub string in Phase 2. Do not add UUID generation yet unless it is trivial and does not broaden the slice.

### Task 1: Add Failing Endpoint Tests

**Files:**
- Create: `tests/unit/test_agent_api_routes.py`
- Read: `src/internhunter/api/app.py`
- Read: `src/internhunter/api/routes/demo_routes.py`
- Read: `src/internhunter/api/schemas/agent.py`

- [ ] **Step 1: Write the failing test file**

```python
from fastapi.testclient import TestClient

from src.internhunter.api.app import app


client = TestClient(app)


def test_agent_ask_endpoint_exists_and_returns_stub_ok():
    response = client.post(
        "/agent/ask",
        json={
            "question": "Show me data scientist jobs in Hanoi.",
            "preview_only": False,
            "include_summary": True,
            "include_chart": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["question"] == "Show me data scientist jobs in Hanoi."
    assert payload["sql"] == {
        "model_generated_sql": None,
        "validated_sql": None,
        "executed_sql": None,
    }
    assert payload["table"] is None
    assert payload["chart"] is None
    assert payload["error"] is None
    assert payload["metadata"]["execution_skipped"] is True


def test_agent_ask_endpoint_rejects_malformed_payload():
    response = client.post(
        "/agent/ask",
        json={
            "question": "   ",
            "limit": 0,
        },
    )

    assert response.status_code == 422


def test_agent_ask_endpoint_returns_preview_envelope_when_requested():
    response = client.post(
        "/agent/ask",
        json={
            "question": "Preview jobs by city.",
            "preview_only": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["sql"]["validated_sql"] == "-- preview stub; no SQL generated yet"
    assert payload["sql"]["executed_sql"] is None
    assert payload["metadata"]["execution_skipped"] is True
    assert payload["table"] is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```powershell
uv run pytest tests\unit\test_agent_api_routes.py -v
```

Expected:
- `404` or import failure because `/agent/ask` is not wired yet

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/unit/test_agent_api_routes.py
git commit -m "test: add failing agent ask endpoint tests"
```

### Task 2: Add The Thin Orchestration Service

**Files:**
- Create: `src/agents/service.py`
- Modify: `src/agents/__init__.py`
- Read: `src/internhunter/api/schemas/agent.py`

- [ ] **Step 1: Write the minimal service module**

```python
from __future__ import annotations

from src.internhunter.api.schemas.agent import (
    AgentAskOkResponse,
    AgentAskPreviewResponse,
    AgentAskRequest,
    AgentResponseMetadata,
    AgentSQLPayload,
)


def handle_agent_ask(request: AgentAskRequest) -> AgentAskOkResponse | AgentAskPreviewResponse:
    metadata = AgentResponseMetadata(
        limit_applied=False,
        execution_skipped=True,
        trace_id="stub-trace-id",
        session_id=request.session_id,
        user_id=request.user_id,
    )

    if request.preview_only:
        return AgentAskPreviewResponse(
            question=request.question,
            sql=AgentSQLPayload(validated_sql="-- preview stub; no SQL generated yet"),
            summary="Preview mode is wired. Real SQL preview is not implemented yet.",
            warnings=["Stub preview only. No SQL was executed."],
            metadata=metadata,
        )

    return AgentAskOkResponse(
        question=request.question,
        sql=AgentSQLPayload(),
        summary="Agent endpoint is wired. Real orchestration is not implemented yet.",
        warnings=["Stub response only. No SQL was generated or executed."],
        metadata=metadata,
    )
```

- [ ] **Step 2: Re-export the service entrypoint if a stable import path is helpful**

```python
from src.agents.service import handle_agent_ask
from src.agents.types import (
    AskRequestArtifact,
    ChartArtifact,
    RefusalArtifact,
    RefusalCategory,
    RefusalCode,
    SqlCandidateArtifact,
    SummaryArtifact,
    TableArtifact,
    ValidatedSqlArtifact,
)

__all__ = [
    "handle_agent_ask",
    "AskRequestArtifact",
    "ChartArtifact",
    "RefusalArtifact",
    "RefusalCategory",
    "RefusalCode",
    "SqlCandidateArtifact",
    "SummaryArtifact",
    "TableArtifact",
    "ValidatedSqlArtifact",
]
```

- [ ] **Step 3: Run the focused tests again**

Run:

```powershell
uv run pytest tests\unit\test_agent_api_routes.py -v
```

Expected:
- still fail because the route is not wired yet, but there should be no import errors from the new service module

- [ ] **Step 4: Commit the service seam**

```bash
git add src/agents/service.py src/agents/__init__.py
git commit -m "feat: add agent orchestration stub service"
```

### Task 3: Add The Agent Route Module

**Files:**
- Create: `src/internhunter/api/routes/agent_routes.py`
- Read: `src/internhunter/api/routes/demo_routes.py`
- Read: `src/agents/service.py`
- Read: `src/internhunter/api/schemas/agent.py`

- [ ] **Step 1: Write the thin route module**

```python
from __future__ import annotations

from fastapi import APIRouter

from src.agents.service import handle_agent_ask
from src.internhunter.api.schemas.agent import (
    AgentAskRequest,
    AgentAskResponse,
)


router = APIRouter()


@router.post("/agent/ask", response_model=AgentAskResponse)
def ask_agent(request: AgentAskRequest) -> AgentAskResponse:
    return handle_agent_ask(request)
```

- [ ] **Step 2: Run the focused tests again**

Run:

```powershell
uv run pytest tests\unit\test_agent_api_routes.py -v
```

Expected:
- still fail because the app is not including the router yet

- [ ] **Step 3: Commit the route module**

```bash
git add src/internhunter/api/routes/agent_routes.py
git commit -m "feat: add agent ask route module"
```

### Task 4: Wire The Router Into The App

**Files:**
- Modify: `src/internhunter/api/app.py`
- Read: `src/internhunter/api/routes/agent_routes.py`
- Read: `src/internhunter/api/routes/demo_routes.py`

- [ ] **Step 1: Update the FastAPI app wiring**

```python
from fastapi import FastAPI

from src.internhunter.api.routes.agent_routes import router as agent_router
from src.internhunter.api.routes.demo_routes import router as demo_router

app = FastAPI(
    title="InternHunter MVP API",
    version="0.1.0",
    description="Minimal local demo API for job search and resume matching.",
)

app.include_router(demo_router)
app.include_router(agent_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "InternHunter MVP API"}
```

- [ ] **Step 2: Run the focused Phase 2 endpoint tests**

Run:

```powershell
uv run pytest tests\unit\test_agent_api_routes.py -v
```

Expected:
- all three tests pass

- [ ] **Step 3: Run the existing demo route tests to verify no regressions**

Run:

```powershell
uv run pytest tests\unit\test_demo_api_routes.py -v
```

Expected:
- all existing demo route tests still pass

- [ ] **Step 4: Commit the app wiring**

```bash
git add src/internhunter/api/app.py
git commit -m "feat: wire agent ask endpoint into api app"
```

### Task 5: Close Phase 2 Checklist And Re-Verify

**Files:**
- Modify: `docs/agent/database_agent_wave1_implementation_plan.md`
- Read: `docs/agent/database_agent_wave1_implementation_plan.md`

- [ ] **Step 1: Update the Phase 2 checklist items**

Mark complete only these items in `### 2. Route And Orchestration Skeleton`:

```markdown
- [x] Add the new route module
- [x] Wire the new route into the FastAPI app
- [x] Add a thin orchestration service entrypoint
- [x] Keep existing routes unchanged
```

And these test items:

```markdown
- [x] endpoint exists
- [x] malformed payload returns `400`
- [x] happy-path stub returns the shared envelope
```

Update the definition-of-done items only if the tests and app wiring prove them.

Note:
- FastAPI/Pydantic validation errors currently surface as `422`, not `400`.
- If the implementation keeps the default FastAPI behavior, update the plan wording to match the actual shipped behavior instead of forcing a custom exception mapper in Phase 2.

- [ ] **Step 2: Run the smallest combined verification set**

Run:

```powershell
uv run pytest tests\unit\test_agent_api_routes.py tests\unit\test_demo_api_routes.py -v
```

Expected:
- both files pass

- [ ] **Step 3: Commit the checklist sync**

```bash
git add docs/agent/database_agent_wave1_implementation_plan.md tests/unit/test_agent_api_routes.py src/agents/service.py src/agents/__init__.py src/internhunter/api/routes/agent_routes.py src/internhunter/api/app.py
git commit -m "docs: close phase 2 route and orchestration skeleton"
```

## Spec Coverage Check

- `POST /agent/ask` added:
  - Task 3 and Task 4
- wire route into FastAPI app:
  - Task 4
- thin orchestration seam:
  - Task 2
- use Phase 1 request/response contract:
  - Task 2 and Task 3
- stub shared envelope:
  - Task 2
- focused tests:
  - Task 1 and Task 4
- existing routes unchanged:
  - Task 4 regression run

No spec gaps found for Phase 2.

## Known Assumptions

- The Phase 2 happy-path stub should not pretend execution happened, so `metadata.execution_skipped=True` is the safest contract-consistent behavior.
- The preview path is lightweight enough to include now because the Phase 1 contract already defines it and it keeps the stub behavior deterministic.
- Refused envelopes stay in the contract but do not need live triggering in this phase because pre-agent guardrails and refusal routing belong to later phases.
- FastAPI model validation defaults to `422 Unprocessable Entity`; if the user still wants `400`, that becomes a new explicit API policy choice and should not be added silently in this slice.

## Risks To Watch During Execution

- Do not let the service layer start making routing decisions beyond `preview_only`.
- Do not add any SQL placeholder that implies `raw_jobs` or broader schema access.
- Do not change existing demo routes or shared ETL/search/resume behavior.
- Do not add UUID generation, tracing utilities, or logger plumbing unless absolutely necessary to satisfy imports.
- Keep the stub text obviously temporary so later phases can replace it without contract confusion.

## Verification Commands

Primary Phase 2 test command:

```powershell
uv run pytest tests\unit\test_agent_api_routes.py -v
```

Regression check:

```powershell
uv run pytest tests\unit\test_demo_api_routes.py -v
```

Combined final check:

```powershell
uv run pytest tests\unit\test_agent_api_routes.py tests\unit\test_demo_api_routes.py -v
```
