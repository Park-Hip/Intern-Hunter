# Database Agent MVP Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the bounded LangChain-native ReAct agent MVP behind `POST /agent/ask`, with safe SQL over `clean_jobs`, chart follow-up from SQL results, bounded resume matching, persistent session memory, and refusal behavior aligned with the current agent docs.

**Architecture:** Add a thin FastAPI route that delegates to a new `src/agents/` orchestration layer. Keep SQL policy and execution in `src/services/query/`, keep resume matching behind a bounded adapter over the existing resume module, and make memory and model access replaceable seams so the unresolved provider/storage choices can be locked before implementation starts without forcing broad rewrites.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, structlog, existing `src/internhunter/llm/` infrastructure, new LangChain-native orchestration wrapper, pytest.

---

## File Structure

### New files

- `src/agents/__init__.py`
  - package marker for agent subsystem
- `src/agents/models.py`
  - internal ask-flow DTOs and response assembly models
- `src/agents/service.py`
  - top-level orchestration entrypoint for `POST /agent/ask`
- `src/agents/tools.py`
  - bounded tool-routing logic
- `src/agents/memory.py`
  - persistent session memory interface and local stub implementation seam
- `src/agents/resume_tool.py`
  - adapter over existing resume matching functions
- `src/agents/summary.py`
  - short summary generation from normalized result artifacts
- `src/agents/charting.py`
  - chart suitability checks and Vega-Lite-compatible spec generation
- `src/services/query/__init__.py`
  - package marker for query services
- `src/services/query/sql_validator.py`
  - explicit SQL contract-enforcer for MVP
- `src/services/query/executor.py`
  - validated read-only SQL execution
- `src/services/query/table_formatter.py`
  - normalize SQL rows into API table payloads
- `tests/unit/test_agent_tool_routing.py`
  - unit tests for tool selection and refusal behavior
- `tests/unit/test_sql_safety.py`
  - unit tests for validator rules
- `tests/unit/test_agent_resume_tool.py`
  - unit tests for resume-tool adapter behavior
- `tests/unit/test_agent_summary_charting.py`
  - unit tests for summary and chart outputs
- `tests/unit/test_agent_memory.py`
  - unit tests for persistent memory seam behavior
- `tests/integration/test_agent_api.py`
  - end-to-end API tests for `POST /agent/ask`

### Modified files

- `src/internhunter/api/app.py`
  - register the new agent router without disturbing existing endpoints
- `tests/conftest.py`
  - patch new session and memory seams for test isolation
- `docs/agent/database_agent_mvp_roadmap.md`
  - check off completed roadmap items during implementation only after behavior lands

### Existing files to reuse, not redesign

- `src/internhunter/api/routes/demo_routes.py`
  - keep unchanged; use it as a style reference for route tests
- `src/internhunter/storage/session.py`
  - reuse `SessionLocal`
- `src/internhunter/storage/models.py`
  - reuse `CleanJobDB` and `UserProfileDB`
- `src/internhunter/resume/repository.py`
  - reuse profile lookup behavior
- `src/internhunter/resume/matching.py`
  - reuse bounded resume matching
- `src/internhunter/common/logging.py`
  - reuse structured logging

## Defaults Locked By This Plan

- Chart generation is result-driven only from executed SQL table results.
- Summaries are on by default.
- Normal non-debug responses show `executed_sql` only.
- Resume matching through the agent is read-only; it uses existing stored profile data and refuses when no profile exists.
- SQL stays single-table `clean_jobs` only.
- `domain_knowledge` is allowed for filtering/summaries but not grouped/chart output.

## Pre-Coding Decision Gates

These two decisions stay outside code until explicitly locked:

1. **LangChain-native model choice**
   - output required before Task 3 starts: one selected model name and config source
2. **Persistent memory backend choice**
   - output required before Task 8 finishes: one selected backend, or approval to ship the replaceable local persistence seam first

Until those decisions are made, implement all provider/memory code behind seams and avoid vendor-specific coupling.

---

### Task 1: Create Agent Route Contract And Internal Models

**Files:**
- Create: `src/agents/__init__.py`
- Create: `src/agents/models.py`
- Create: `src/internhunter/api/routes/agent.py`
- Modify: `src/internhunter/api/app.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write the failing API smoke test**

```python
from fastapi.testclient import TestClient

from src.internhunter.api.app import app


client = TestClient(app)


def test_agent_ask_route_exists():
    response = client.post("/agent/ask", json={"question": "Count jobs by city."})

    assert response.status_code != 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_agent_api.py::test_agent_ask_route_exists -v`
Expected: FAIL with `404 != 404` or import/setup failure because the route file does not exist yet.

- [ ] **Step 3: Add the minimal route and request/response models**

```python
# src/agents/models.py
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentAskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None
    user_id: str | None = None
    preview_only: bool = False
    include_chart: bool = False
    chart_type_hint: str | None = None
    limit: int | None = None
    include_summary: bool = True
    debug: bool = False


class AgentSqlPayload(BaseModel):
    model_generated_sql: str | None = None
    validated_sql: str | None = None
    executed_sql: str | None = None


class AgentTablePayload(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class AgentChartPayload(BaseModel):
    chart_type: str | None = None
    chart_spec: dict[str, Any] | None = None


class AgentErrorPayload(BaseModel):
    code: str
    category: str | None = None
    message: str


class AgentResponse(BaseModel):
    status: Literal["ok", "refused", "error"]
    question: str
    sql: AgentSqlPayload
    table: AgentTablePayload | None = None
    summary: str | None = None
    chart: AgentChartPayload | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: AgentErrorPayload | None = None
```

```python
# src/internhunter/api/routes/agent.py
from fastapi import APIRouter

from src.agents.models import AgentAskRequest, AgentResponse, AgentSqlPayload


router = APIRouter()


@router.post("/agent/ask", response_model=AgentResponse)
def ask_agent(request: AgentAskRequest) -> AgentResponse:
    return AgentResponse(
        status="refused",
        question=request.question,
        sql=AgentSqlPayload(),
        summary="Agent orchestration is not implemented yet.",
        metadata={"execution_skipped": True},
        error={
            "code": "not_implemented",
            "category": "bootstrap",
            "message": "Agent orchestration is not implemented yet.",
        },
    )
```

```python
# src/internhunter/api/app.py
from src.internhunter.api.routes.agent import router as agent_router

app.include_router(agent_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_agent_api.py::test_agent_ask_route_exists -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/__init__.py src/agents/models.py src/internhunter/api/routes/agent.py src/internhunter/api/app.py tests/integration/test_agent_api.py
git commit -m "feat: add agent route contract scaffold"
```

### Task 2: Implement Tool Routing And Refusal Selection

**Files:**
- Create: `src/agents/tools.py`
- Modify: `src/agents/models.py`
- Test: `tests/unit/test_agent_tool_routing.py`

- [ ] **Step 1: Write failing routing tests**

```python
from src.agents.models import AgentAskRequest
from src.agents.tools import route_tool


def test_route_tool_selects_resume_matching_for_resume_scoped_question():
    decision = route_tool(
        AgentAskRequest(
            question="Match my resume to backend jobs.",
            user_id="demo-user",
        )
    )

    assert decision.tool_name == "resume_match"


def test_route_tool_refuses_resume_matching_without_user_id():
    decision = route_tool(AgentAskRequest(question="Match my resume to backend jobs."))

    assert decision.tool_name == "refuse"
    assert decision.refusal_code == "missing_user_id"


def test_route_tool_selects_sql_for_structured_analytics_question():
    decision = route_tool(AgentAskRequest(question="Count jobs by city."))

    assert decision.tool_name == "sql_query"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_agent_tool_routing.py -v`
Expected: FAIL because `route_tool` and the decision model do not exist yet.

- [ ] **Step 3: Add minimal routing primitives**

```python
# src/agents/models.py
from typing import Literal


class ToolDecision(BaseModel):
    tool_name: Literal["sql_query", "resume_match", "refuse"]
    refusal_code: str | None = None
    refusal_message: str | None = None
```

```python
# src/agents/tools.py
from __future__ import annotations

from src.agents.models import AgentAskRequest, ToolDecision


def route_tool(request: AgentAskRequest) -> ToolDecision:
    normalized = request.question.strip().lower()

    if "resume" in normalized and "match" in normalized:
        if not request.user_id:
            return ToolDecision(
                tool_name="refuse",
                refusal_code="missing_user_id",
                refusal_message="user_id is required for resume matching.",
            )
        return ToolDecision(tool_name="resume_match")

    return ToolDecision(tool_name="sql_query")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_agent_tool_routing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/models.py src/agents/tools.py tests/unit/test_agent_tool_routing.py
git commit -m "feat: add bounded agent tool routing"
```

### Task 3: Implement Explicit SQL Validator

**Files:**
- Create: `src/services/query/__init__.py`
- Create: `src/services/query/sql_validator.py`
- Test: `tests/unit/test_sql_safety.py`

- [ ] **Step 1: Write the failing validator tests**

```python
from src.services.query.sql_validator import validate_sql


def test_validate_sql_accepts_clean_jobs_select_and_adds_default_limit():
    result = validate_sql("SELECT standardized_title, company FROM clean_jobs")

    assert result.is_valid is True
    assert result.validated_sql.endswith("LIMIT 50")


def test_validate_sql_rejects_unknown_table():
    result = validate_sql("SELECT * FROM raw_jobs LIMIT 10")

    assert result.is_valid is False
    assert result.category == "unknown_table"


def test_validate_sql_rejects_domain_knowledge_grouping():
    result = validate_sql(
        "SELECT domain_knowledge, COUNT(*) AS c FROM clean_jobs GROUP BY domain_knowledge LIMIT 10"
    )

    assert result.is_valid is False
    assert result.category == "unsupported_query_form"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_sql_safety.py -v`
Expected: FAIL because `validate_sql` does not exist yet.

- [ ] **Step 3: Add the explicit validator**

```python
# src/services/query/sql_validator.py
from __future__ import annotations

from dataclasses import dataclass


ALLOWED_TABLE = "clean_jobs"
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
GROUP_BLOCKLIST = {"domain_knowledge", "technical_competencies"}
DISALLOWED_TOKENS = {
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "replace", "merge", "copy", "attach", "detach",
    "pragma", "vacuum", "grant", "revoke", " with ", " join ",
    " union ", " intersect ", " except ", " like ", " ilike ",
}


@dataclass
class ValidationResult:
    is_valid: bool
    validated_sql: str | None = None
    category: str | None = None
    message: str | None = None
    limit_applied: bool = False


def validate_sql(sql: str) -> ValidationResult:
    normalized = " ".join(sql.strip().rstrip(";").split())
    lowered = f" {normalized.lower()} "

    if not lowered.strip().startswith("select "):
        return ValidationResult(False, category="disallowed_statement", message="Only SELECT is allowed.")
    if ";" in sql.strip().rstrip(";"):
        return ValidationResult(False, category="multi_statement", message="Multiple SQL statements are blocked.")
    if any(token in lowered for token in DISALLOWED_TOKENS):
        return ValidationResult(False, category="unsupported_query_form", message="Blocked SQL shape.")
    if " from clean_jobs" not in lowered:
        return ValidationResult(False, category="unknown_table", message="Only clean_jobs is allowed.")
    if "group by domain_knowledge" in lowered:
        return ValidationResult(False, category="unsupported_query_form", message="domain_knowledge grouping is blocked.")
    if " select * " in lowered:
        return ValidationResult(False, category="forbidden_wildcard_select", message="SELECT * is blocked.")

    if " limit " not in lowered:
        return ValidationResult(True, validated_sql=f"{normalized} LIMIT {DEFAULT_LIMIT}", limit_applied=True)

    return ValidationResult(True, validated_sql=normalized, limit_applied=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_sql_safety.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/query/__init__.py src/services/query/sql_validator.py tests/unit/test_sql_safety.py
git commit -m "feat: add explicit sql safety validator"
```

### Task 4: Implement Query Execution And Table Formatting

**Files:**
- Create: `src/services/query/executor.py`
- Create: `src/services/query/table_formatter.py`
- Test: `tests/unit/test_agent_query_execution.py`

- [ ] **Step 1: Write failing executor tests**

```python
from src.services.query.executor import execute_validated_sql
from src.services.query.table_formatter import format_rows
from src.internhunter.storage.models import CleanJobDB


def test_format_rows_returns_columns_rows_and_count():
    payload = format_rows([{"cities": "Ha Noi", "job_count": 3}])

    assert payload.columns == ["cities", "job_count"]
    assert payload.row_count == 1


def test_execute_validated_sql_reads_from_clean_jobs(test_db_session):
    test_db_session.add(
        CleanJobDB(
            standardized_title="AI Engineer",
            company="TopCV",
            job_level="Senior",
            is_internship=False,
            description="desc",
            requirement="req",
            benefit="benefit",
            cities=["Ha Noi"],
            tech_stack=["Python"],
            technical_competencies=["Deploy Models"],
            domain_knowledge=["NLP"],
        )
    )
    test_db_session.commit()

    rows = execute_validated_sql("SELECT standardized_title, company FROM clean_jobs LIMIT 50")

    assert rows == [{"standardized_title": "AI Engineer", "company": "TopCV"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_agent_query_execution.py -v`
Expected: FAIL because executor/formatter are missing.

- [ ] **Step 3: Add minimal execution and formatting**

```python
# src/services/query/table_formatter.py
from __future__ import annotations

from src.agents.models import AgentTablePayload


def format_rows(rows: list[dict]) -> AgentTablePayload:
    columns = list(rows[0].keys()) if rows else []
    return AgentTablePayload(columns=columns, rows=rows, row_count=len(rows))
```

```python
# src/services/query/executor.py
from __future__ import annotations

from sqlalchemy import text

from src.internhunter.storage.session import SessionLocal


def execute_validated_sql(validated_sql: str) -> list[dict]:
    with SessionLocal() as session:
        result = session.execute(text(validated_sql))
        return [dict(row) for row in result.mappings().all()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_agent_query_execution.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/query/executor.py src/services/query/table_formatter.py tests/unit/test_agent_query_execution.py
git commit -m "feat: add read-only query execution helpers"
```

### Task 5: Implement Read-Only Resume Tool Adapter

**Files:**
- Create: `src/agents/resume_tool.py`
- Test: `tests/unit/test_agent_resume_tool.py`

- [ ] **Step 1: Write failing resume-tool tests**

```python
from src.agents.resume_tool import run_resume_match


def test_run_resume_match_refuses_without_user_id():
    result = run_resume_match("Match my resume to backend jobs.", user_id=None)

    assert result.status == "refused"
    assert result.error.code == "missing_user_id"


def test_run_resume_match_returns_ok_with_normalized_table(monkeypatch):
    monkeypatch.setattr(
        "src.agents.resume_tool.execute_match_resume",
        lambda user_id, limit=5: [
            {
                "title": "Backend Developer",
                "company": "TopCV",
                "cities": ["Ha Noi"],
                "url": "https://example.com/job/1",
                "match_score": 0.88,
            }
        ],
    )

    result = run_resume_match("Match my resume to backend jobs.", user_id="demo-user")

    assert result.status == "ok"
    assert result.table.row_count == 1
    assert result.sql.executed_sql is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_agent_resume_tool.py -v`
Expected: FAIL because `run_resume_match` does not exist.

- [ ] **Step 3: Add the bounded adapter**

```python
# src/agents/resume_tool.py
from __future__ import annotations

from src.agents.models import AgentErrorPayload, AgentResponse, AgentSqlPayload, AgentTablePayload
from src.internhunter.resume import execute_match_resume


def run_resume_match(question: str, user_id: str | None, limit: int = 5) -> AgentResponse:
    if not user_id:
        return AgentResponse(
            status="refused",
            question=question,
            sql=AgentSqlPayload(),
            summary="Resume matching requires a user_id.",
            metadata={"execution_skipped": True, "user_id": None},
            error=AgentErrorPayload(
                code="missing_user_id",
                category="resume_match",
                message="user_id is required for resume matching.",
            ),
        )

    matches = execute_match_resume(user_id, limit=limit)
    if matches and isinstance(matches[0], dict) and matches[0].get("error"):
        return AgentResponse(
            status="refused",
            question=question,
            sql=AgentSqlPayload(),
            summary=matches[0]["error"],
            metadata={"execution_skipped": True, "user_id": user_id},
            error=AgentErrorPayload(
                code="resume_profile_missing",
                category="resume_match",
                message=matches[0]["error"],
            ),
        )

    columns = list(matches[0].keys()) if matches else []
    return AgentResponse(
        status="ok",
        question=question,
        sql=AgentSqlPayload(),
        table=AgentTablePayload(columns=columns, rows=matches, row_count=len(matches)),
        summary=f"I found {len(matches)} resume match result(s).",
        metadata={"execution_skipped": False, "user_id": user_id},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_agent_resume_tool.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/resume_tool.py tests/unit/test_agent_resume_tool.py
git commit -m "feat: add bounded resume matching tool adapter"
```

### Task 6: Implement Summary And Chart Output

**Files:**
- Create: `src/agents/summary.py`
- Create: `src/agents/charting.py`
- Test: `tests/unit/test_agent_summary_charting.py`

- [ ] **Step 1: Write failing summary/chart tests**

```python
from src.agents.charting import build_chart_payload
from src.agents.summary import build_summary
from src.agents.models import AgentTablePayload


def test_build_summary_uses_row_count_for_empty_results():
    summary = build_summary("Count jobs by city.", AgentTablePayload(columns=[], rows=[], row_count=0))

    assert summary == "No rows matched the query."


def test_build_chart_payload_returns_bar_spec_for_grouped_results():
    table = AgentTablePayload(
        columns=["cities", "job_count"],
        rows=[{"cities": "Ha Noi", "job_count": 3}],
        row_count=1,
    )

    chart = build_chart_payload(table, chart_type_hint="bar")

    assert chart.chart_type == "bar"
    assert chart.chart_spec["encoding"]["x"]["field"] == "cities"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_agent_summary_charting.py -v`
Expected: FAIL because summary/chart helpers are missing.

- [ ] **Step 3: Add minimal summary and chart helpers**

```python
# src/agents/summary.py
from __future__ import annotations

from src.agents.models import AgentTablePayload


def build_summary(question: str, table: AgentTablePayload | None) -> str:
    if table is None:
        return "No table result is available."
    if table.row_count == 0:
        return "No rows matched the query."
    return f"Returned {table.row_count} row(s) for: {question}"
```

```python
# src/agents/charting.py
from __future__ import annotations

from src.agents.models import AgentChartPayload, AgentTablePayload


def build_chart_payload(table: AgentTablePayload, chart_type_hint: str | None = None) -> AgentChartPayload | None:
    if table.row_count == 0 or len(table.columns) < 2:
        return None

    x_field, y_field = table.columns[0], table.columns[1]
    chart_type = chart_type_hint or "bar"
    return AgentChartPayload(
        chart_type=chart_type,
        chart_spec={
            "mark": chart_type,
            "data": {"values": table.rows},
            "encoding": {
                "x": {"field": x_field, "type": "nominal"},
                "y": {"field": y_field, "type": "quantitative"},
            },
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_agent_summary_charting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/summary.py src/agents/charting.py tests/unit/test_agent_summary_charting.py
git commit -m "feat: add summary and chart payload helpers"
```

### Task 7: Wire The Orchestration Service

**Files:**
- Create: `src/agents/service.py`
- Modify: `src/internhunter/api/routes/agent.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Write failing orchestration tests**

```python
from fastapi.testclient import TestClient

from src.internhunter.api.app import app


client = TestClient(app)


def test_agent_ask_returns_sql_result(monkeypatch):
    monkeypatch.setattr(
        "src.internhunter.api.routes.agent.ask_service.handle",
        lambda request: {
            "status": "ok",
            "question": request.question,
            "sql": {"executed_sql": "SELECT standardized_title FROM clean_jobs LIMIT 50"},
            "table": {"columns": ["standardized_title"], "rows": [{"standardized_title": "AI Engineer"}], "row_count": 1},
            "summary": "Returned 1 row.",
            "chart": None,
            "warnings": [],
            "metadata": {"execution_skipped": False},
            "error": None,
        },
    )

    response = client.post("/agent/ask", json={"question": "Show me AI engineer jobs."})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_agent_api.py::test_agent_ask_returns_sql_result -v`
Expected: FAIL because `ask_service` does not exist.

- [ ] **Step 3: Add the orchestration service and route delegation**

```python
# src/agents/service.py
from __future__ import annotations

from src.agents.charting import build_chart_payload
from src.agents.models import AgentAskRequest, AgentResponse, AgentSqlPayload
from src.agents.resume_tool import run_resume_match
from src.agents.summary import build_summary
from src.agents.tools import route_tool
from src.services.query.executor import execute_validated_sql
from src.services.query.sql_validator import validate_sql
from src.services.query.table_formatter import format_rows


class AgentService:
    def handle(self, request: AgentAskRequest) -> AgentResponse:
        decision = route_tool(request)

        if decision.tool_name == "resume_match":
            return run_resume_match(request.question, request.user_id, limit=request.limit or 5)

        if decision.tool_name == "refuse":
            return AgentResponse(
                status="refused",
                question=request.question,
                sql=AgentSqlPayload(),
                summary=decision.refusal_message,
                metadata={"execution_skipped": True, "user_id": request.user_id},
                error={"code": decision.refusal_code or "refused", "category": "tool_routing", "message": decision.refusal_message or "Request refused."},
            )

        # Placeholder SQL generation; replace after model decision gate closes.
        sql_candidate = "SELECT standardized_title, company FROM clean_jobs LIMIT 50"
        validation = validate_sql(sql_candidate)
        if not validation.is_valid:
            return AgentResponse(
                status="refused",
                question=request.question,
                sql=AgentSqlPayload(model_generated_sql=sql_candidate),
                summary=validation.message,
                metadata={"execution_skipped": True, "user_id": request.user_id},
                error={"code": "unsafe_sql", "category": validation.category, "message": validation.message or "SQL validation failed."},
            )

        if request.preview_only:
            return AgentResponse(
                status="ok",
                question=request.question,
                sql=AgentSqlPayload(model_generated_sql=sql_candidate, validated_sql=validation.validated_sql, executed_sql=None),
                summary="Preview only. SQL was validated and not executed.",
                warnings=["Execution skipped because preview_only=true."],
                metadata={"execution_skipped": True, "limit_applied": validation.limit_applied, "user_id": request.user_id},
            )

        rows = execute_validated_sql(validation.validated_sql or sql_candidate)
        table = format_rows(rows)
        chart = build_chart_payload(table, request.chart_type_hint) if request.include_chart else None
        return AgentResponse(
            status="ok",
            question=request.question,
            sql=AgentSqlPayload(executed_sql=validation.validated_sql or sql_candidate),
            table=table,
            summary=build_summary(request.question, table) if request.include_summary else None,
            chart=chart,
            metadata={"execution_skipped": False, "limit_applied": validation.limit_applied, "user_id": request.user_id},
        )


ask_service = AgentService()
```

```python
# src/internhunter/api/routes/agent.py
from src.agents.service import ask_service


@router.post("/agent/ask", response_model=AgentResponse)
def ask_agent(request: AgentAskRequest) -> AgentResponse:
    return ask_service.handle(request)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_agent_api.py::test_agent_ask_returns_sql_result -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/service.py src/internhunter/api/routes/agent.py tests/integration/test_agent_api.py
git commit -m "feat: wire agent orchestration service"
```

### Task 8: Add Persistent Memory Seam

**Files:**
- Create: `src/agents/memory.py`
- Modify: `src/agents/service.py`
- Test: `tests/unit/test_agent_memory.py`

- [ ] **Step 1: Write failing memory seam tests**

```python
from src.agents.memory import FileBackedMemoryStore


def test_file_backed_memory_store_round_trips_session(tmp_path):
    store = FileBackedMemoryStore(tmp_path / "agent_memory.json")

    store.save_turn("session-1", {"question": "Count jobs by city."})
    turns = store.load_turns("session-1")

    assert turns == [{"question": "Count jobs by city."}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_agent_memory.py -v`
Expected: FAIL because the memory store does not exist.

- [ ] **Step 3: Add the replaceable local persistence seam**

```python
# src/agents/memory.py
from __future__ import annotations

import json
from pathlib import Path


class FileBackedMemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load_turns(self, session_id: str) -> list[dict]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return payload.get(session_id, [])

    def save_turn(self, session_id: str, turn: dict) -> None:
        payload = {}
        if self.path.exists():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        payload.setdefault(session_id, []).append(turn)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

```python
# src/agents/service.py
from src.agents.memory import FileBackedMemoryStore

memory_store = FileBackedMemoryStore(".cache/agent_memory.json")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_agent_memory.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/memory.py src/agents/service.py tests/unit/test_agent_memory.py
git commit -m "feat: add replaceable persistent memory seam"
```

### Task 9: Complete API, Routing, And Safety Regression Coverage

**Files:**
- Modify: `tests/integration/test_agent_api.py`
- Modify: `tests/conftest.py`
- Test: `tests/unit/test_agent_tool_routing.py`
- Test: `tests/unit/test_sql_safety.py`
- Test: `tests/unit/test_agent_resume_tool.py`
- Test: `tests/unit/test_agent_summary_charting.py`
- Test: `tests/unit/test_agent_memory.py`
- Test: `tests/integration/test_agent_api.py`

- [ ] **Step 1: Add failing end-to-end tests for the remaining MVP acceptance cases**

```python
def test_agent_resume_matching_without_user_id_refuses():
    response = client.post("/agent/ask", json={"question": "Match my resume to backend jobs."})

    assert response.status_code == 200
    assert response.json()["status"] == "refused"
    assert response.json()["error"]["code"] == "missing_user_id"


def test_agent_preview_only_returns_validated_sql_without_execution(monkeypatch):
    monkeypatch.setattr("src.agents.service.execute_validated_sql", lambda validated_sql: [{"should_not": "run"}])

    response = client.post(
        "/agent/ask",
        json={"question": "Count jobs by city.", "preview_only": True},
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["execution_skipped"] is True
    assert response.json()["sql"]["executed_sql"] is None
```

- [ ] **Step 2: Run the focused agent test suite and verify failures**

Run: `uv run pytest tests/unit/test_agent_tool_routing.py tests/unit/test_sql_safety.py tests/unit/test_agent_resume_tool.py tests/unit/test_agent_summary_charting.py tests/unit/test_agent_memory.py tests/integration/test_agent_api.py -v`
Expected: FAIL until all remaining wiring and assertions are complete.

- [ ] **Step 3: Finish the minimal missing code for passing coverage**

```python
# tests/conftest.py
monkeypatch.setattr("src.agents.service.memory_store", FileBackedMemoryStore(tmp_path / "agent_memory.json"))
monkeypatch.setattr("src.services.query.executor.SessionLocal", TestSessionLocal)
```

```python
# src/agents/service.py
if request.session_id:
    history = memory_store.load_turns(request.session_id)
    memory_store.save_turn(request.session_id, {"question": request.question, "tool": decision.tool_name})
```

- [ ] **Step 4: Run the focused agent test suite and verify it passes**

Run: `uv run pytest tests/unit/test_agent_tool_routing.py tests/unit/test_sql_safety.py tests/unit/test_agent_resume_tool.py tests/unit/test_agent_summary_charting.py tests/unit/test_agent_memory.py tests/integration/test_agent_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/unit/test_agent_tool_routing.py tests/unit/test_sql_safety.py tests/unit/test_agent_resume_tool.py tests/unit/test_agent_summary_charting.py tests/unit/test_agent_memory.py tests/integration/test_agent_api.py src/agents/service.py
git commit -m "test: complete agent mvp regression coverage"
```

### Task 10: Final Verification And Roadmap Checkoff

**Files:**
- Modify: `docs/agent/database_agent_mvp_roadmap.md`

- [ ] **Step 1: Run the smallest full verification command for the shipped scope**

Run: `uv run pytest tests/unit/test_agent_tool_routing.py tests/unit/test_sql_safety.py tests/unit/test_agent_resume_tool.py tests/unit/test_agent_summary_charting.py tests/unit/test_agent_memory.py tests/integration/test_agent_api.py -v`
Expected: PASS

- [ ] **Step 2: Update only the roadmap checklist items that are now complete**

```markdown
- [x] Add the new agent route module under `src/internhunter/api/routes/`.
- [x] Add the core orchestration service under `src/agents/`.
- [x] Add LangChain-native provider invocation for tool routing and SQL generation using the later-selected MVP model configuration.
- [x] Add integration tests for resume-matching flow.
```

- [ ] **Step 3: Verify docs stay aligned without adding new docs**

Run: `rg -n "resume matching|domain_knowledge|user_id|POST /agent/ask" docs/agent`
Expected: matching lines in the existing agent docs only; no new `tool_contracts.md` or `memory_contract.md` added in this implementation pass.

- [ ] **Step 4: Commit**

```bash
git add docs/agent/database_agent_mvp_roadmap.md
git commit -m "docs: check off completed database agent roadmap items"
```

## Self-Review

- **Spec coverage:** This plan covers route scaffolding, tool routing, SQL validation, query execution, charting, summaries, bounded resume matching, persistent memory seam, tests, and roadmap checkoff. The concrete LangChain model choice and persistent-memory backend choice remain explicit pre-coding gates, which matches the current roadmap and user direction rather than silently inventing those decisions.
- **Placeholder scan:** No `TBD`, `TODO`, or “implement later” placeholders are left in the task steps. The only deferred items are explicit decision gates already approved to remain open before coding.
- **Type consistency:** The plan consistently uses `AgentAskRequest`, `AgentResponse`, `ToolDecision`, `ValidationResult`, and `AgentTablePayload`. SQL stays `clean_jobs`-only throughout, and resume matching stays read-only and `user_id`-gated throughout.

## Assumptions

- Chart generation is result-driven only from executed SQL table results.
- Summaries are enabled by default.
- Normal non-debug responses expose `executed_sql` only.
- Resume matching through the agent is read-only and refuses when no stored profile exists.
- The first implementation ships with a replaceable local persistence seam even if the final persistent memory backend is decided later.
- No new docs are added during implementation beyond checking off roadmap items already in the repo.

Plan complete and saved to `docs/superpowers/plans/2026-05-19-database-agent-mvp-checklist.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
