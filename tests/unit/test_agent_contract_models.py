from __future__ import annotations

import pytest
from pydantic import ValidationError

import src.agents as agent_types_module
from src.agents.types import (
    AskRequestArtifact,
    ChartArtifact,
    GuardrailDecision,
    RefusalArtifact,
    RefusalCategory,
    RefusalCode,
    SummaryArtifact,
    TableArtifact,
    ValidatedSqlArtifact,
)
from src.internhunter.api.schemas.agent import (
    AgentAskOkResponse,
    AgentAskPreviewResponse,
    AgentAskRefusedResponse,
    AgentAskRequest,
    AgentErrorPayload,
    AgentResponseMetadata,
    AgentSQLPayload,
)


def test_agent_ask_request_normalizes_optional_ids_and_defaults():
    request = AgentAskRequest(
        question="  Count jobs by city.  ",
        session_id="  session-1  ",
        user_id="   ",
    )

    assert request.question == "Count jobs by city."
    assert request.session_id == "session-1"
    assert request.user_id is None
    assert request.include_summary is True
    assert request.include_chart is False
    assert request.preview_only is False


def test_agent_ask_request_rejects_invalid_question_and_extra_fields():
    with pytest.raises(ValidationError):
        AgentAskRequest(question="   ")

    with pytest.raises(ValidationError):
        AgentAskRequest(question="hello", unsupported=True)


def test_agent_ask_request_rejects_chart_type_hint_and_invalid_limit():
    with pytest.raises(ValidationError):
        AgentAskRequest(question="hello", chart_type_hint="bar")

    with pytest.raises(ValidationError):
        AgentAskRequest(question="hello", limit=0)


def test_table_artifact_requires_row_count_match():
    with pytest.raises(ValidationError):
        TableArtifact(columns=["city"], rows=[{"city": "Ha Noi"}], row_count=0)


def test_internal_artifacts_validate_and_serialize():
    request_artifact = AskRequestArtifact(
        question=" Show me AI engineer jobs in Hanoi. ",
        session_id=" demo-session ",
        include_chart=True,
    )
    table_artifact = TableArtifact(
        columns=["standardized_title", "company"],
        rows=[{"standardized_title": "AI Engineer", "company": "TopCV"}],
        row_count=1,
    )
    summary_artifact = SummaryArtifact(text=" Found 1 matching role. ")
    chart_artifact = ChartArtifact(
        chart_type="bar",
        chart_spec={"mark": "bar", "encoding": {}},
    )
    validated_sql = ValidatedSqlArtifact(
        model_generated_sql="SELECT standardized_title FROM clean_jobs",
        validated_sql="SELECT standardized_title FROM clean_jobs LIMIT 50",
        executed_sql="SELECT standardized_title FROM clean_jobs LIMIT 50",
        limit_applied=True,
    )
    refusal_artifact = RefusalArtifact(
        code=RefusalCode.UNSAFE_SQL,
        category=RefusalCategory.DISALLOWED_STATEMENT,
        message=" blocked ",
    )
    guardrail = GuardrailDecision(allowed=True)

    assert request_artifact.question == "Show me AI engineer jobs in Hanoi."
    assert request_artifact.session_id == "demo-session"
    assert validated_sql.executed_sql == "SELECT standardized_title FROM clean_jobs LIMIT 50"
    assert table_artifact.row_count == 1
    assert summary_artifact.text == "Found 1 matching role."
    assert chart_artifact.chart_type == "bar"
    assert refusal_artifact.message == "blocked"
    assert guardrail.allowed is True


def test_preview_response_serialization():
    response = AgentAskPreviewResponse(
        question="Show me AI engineer jobs in Hanoi.",
        sql=AgentSQLPayload(
            model_generated_sql="SELECT standardized_title FROM clean_jobs",
            validated_sql="SELECT standardized_title FROM clean_jobs LIMIT 50",
            executed_sql=None,
        ),
        summary="Preview only. SQL was validated and not executed.",
        metadata=AgentResponseMetadata(
            limit_applied=True,
            execution_skipped=True,
            trace_id="trace-preview-1",
            session_id="demo-session-123",
            user_id=None,
        ),
        warnings=["Execution skipped because preview_only=true."],
    )

    payload = response.model_dump(mode="json")

    assert payload["status"] == "ok"
    assert payload["sql"]["validated_sql"] == "SELECT standardized_title FROM clean_jobs LIMIT 50"
    assert payload["sql"]["executed_sql"] is None
    assert payload["table"] is None
    assert payload["chart"] is None
    assert payload["metadata"]["execution_skipped"] is True


def test_preview_response_requires_validated_sql_and_execution_skipped():
    with pytest.raises(ValidationError):
        AgentAskPreviewResponse(
            question="Show me AI engineer jobs in Hanoi.",
            sql=AgentSQLPayload(model_generated_sql="SELECT 1"),
            metadata=AgentResponseMetadata(
                limit_applied=False,
                execution_skipped=True,
                trace_id="trace-preview-2",
            ),
        )

    with pytest.raises(ValidationError):
        AgentAskPreviewResponse(
            question="Show me AI engineer jobs in Hanoi.",
            sql=AgentSQLPayload(validated_sql="SELECT 1 LIMIT 50"),
            metadata=AgentResponseMetadata(
                limit_applied=False,
                execution_skipped=False,
                trace_id="trace-preview-3",
            ),
        )


def test_refused_response_serialization():
    response = AgentAskRefusedResponse(
        question="Delete all jobs from the database.",
        sql=AgentSQLPayload(),
        summary="I can only help with safe read-only exploration of clean_jobs in MVP.",
        metadata=AgentResponseMetadata(
            limit_applied=False,
            execution_skipped=True,
            trace_id="trace-refused-1",
        ),
        error=AgentErrorPayload(
            code=RefusalCode.UNSAFE_SQL,
            category=RefusalCategory.DISALLOWED_STATEMENT,
            message="Query rejected because it attempts a non-read-only database operation.",
        ),
    )

    payload = response.model_dump(mode="json")

    assert payload["status"] == "refused"
    assert payload["error"]["code"] == "unsafe_sql"
    assert payload["error"]["category"] == "disallowed_statement"
    assert payload["metadata"]["trace_id"] == "trace-refused-1"


def test_refused_response_requires_error_and_skipped_execution():
    with pytest.raises(ValidationError):
        AgentAskRefusedResponse(
            question="Delete all jobs from the database.",
            sql=AgentSQLPayload(),
            metadata=AgentResponseMetadata(
                limit_applied=False,
                execution_skipped=True,
                trace_id="trace-refused-2",
            ),
        )

    with pytest.raises(ValidationError):
        AgentAskRefusedResponse(
            question="Delete all jobs from the database.",
            sql=AgentSQLPayload(),
            metadata=AgentResponseMetadata(
                limit_applied=False,
                execution_skipped=False,
                trace_id="trace-refused-3",
            ),
            error=AgentErrorPayload(
                code=RefusalCode.UNSAFE_SQL,
                category=RefusalCategory.DISALLOWED_STATEMENT,
                message="blocked",
            ),
        )


def test_ok_response_serialization_supports_sql_and_table_payloads():
    response = AgentAskOkResponse(
        question="Count jobs by city.",
        sql=AgentSQLPayload(executed_sql="SELECT cities, COUNT(*) AS job_count FROM clean_jobs GROUP BY cities LIMIT 100"),
        table=TableArtifact(
            columns=["cities", "job_count"],
            rows=[{"cities": "Ha Noi", "job_count": 12}],
            row_count=1,
        ),
        summary="Ha Noi has 12 jobs in the current database.",
        chart=ChartArtifact(chart_type="bar", chart_spec={"mark": "bar", "encoding": {}}),
        metadata=AgentResponseMetadata(
            limit_applied=True,
            execution_skipped=False,
            trace_id="trace-ok-1",
            session_id="demo-session-123",
            user_id="demo-user-123",
        ),
    )

    payload = response.model_dump(mode="json")

    assert payload["status"] == "ok"
    assert payload["sql"]["executed_sql"] == "SELECT cities, COUNT(*) AS job_count FROM clean_jobs GROUP BY cities LIMIT 100"
    assert payload["table"]["columns"] == ["cities", "job_count"]
    assert payload["metadata"]["user_id"] == "demo-user-123"


def test_internal_types_module_exposes_only_minimal_phase_one_baseline():
    assert hasattr(agent_types_module, "AskRequestArtifact")
    assert hasattr(agent_types_module, "SqlCandidateArtifact")
    assert hasattr(agent_types_module, "ValidatedSqlArtifact")
    assert hasattr(agent_types_module, "TableArtifact")
    assert hasattr(agent_types_module, "RefusalArtifact")
    assert hasattr(agent_types_module, "ChartArtifact")
    assert hasattr(agent_types_module, "SummaryArtifact")
    assert hasattr(agent_types_module, "GuardrailDecision")
    assert not hasattr(agent_types_module, "AgentBranch")
    assert not hasattr(agent_types_module, "RouteDecision")
    assert not hasattr(agent_types_module, "AskResultArtifact")
