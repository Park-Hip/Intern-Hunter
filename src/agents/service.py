from __future__ import annotations

from src.agents.guardrail import screen_question
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


def _build_metadata(request: AgentAskRequest) -> AgentResponseMetadata:
    return AgentResponseMetadata(
        limit_applied=False,
        execution_skipped=True,
        trace_id="stub-trace-id",
        session_id=request.session_id,
        user_id=request.user_id,
    )


def _to_request_artifact(request: AgentAskRequest) -> AskRequestArtifact:
    return AskRequestArtifact(
        question=request.question,
        session_id=request.session_id,
        user_id=request.user_id,
        preview_only=request.preview_only,
    )


def _build_refused_response(
    request: AgentAskRequest,
    refusal: RefusalArtifact,
    summary: str,
) -> AgentAskRefusedResponse:
    return AgentAskRefusedResponse(
        question=request.question,
        sql=AgentSQLPayload(),
        summary=summary,
        warnings=["Request refused before agent execution."],
        metadata=_build_metadata(request),
        error=AgentErrorPayload(
            code=refusal.code,
            category=refusal.category,
            message=refusal.message,
        ),
    )


def _build_preview_response(request: AgentAskRequest) -> AgentAskPreviewResponse:
    return AgentAskPreviewResponse(
        question=request.question,
        sql=AgentSQLPayload(validated_sql="-- preview stub; no SQL generated yet"),
        summary="Preview mode is wired. Real SQL preview is not implemented yet.",
        warnings=["Stub preview only. No SQL was executed."],
        metadata=_build_metadata(request),
    )


def _build_allowed_placeholder_response(request: AgentAskRequest) -> AgentAskOkResponse:
    return AgentAskOkResponse(
        question=request.question,
        sql=AgentSQLPayload(),
        summary="Agent endpoint is guardrailed. Real orchestration is not implemented yet.",
        warnings=["Stub response only. No SQL was generated or executed."],
        metadata=_build_metadata(request),
    )


def handle_agent_ask(
    request: AgentAskRequest,
) -> AgentAskOkResponse | AgentAskPreviewResponse | AgentAskRefusedResponse:
    artifact = _to_request_artifact(request)
    guardrail = screen_question(artifact.question)

    if not guardrail.allowed:
        return _build_refused_response(
            request=request,
            refusal=guardrail.refusal,
            summary="Request refused by the pre-agent guardrail before any branch execution.",
        )

    if request.preview_only:
        return _build_preview_response(request)

    return _build_allowed_placeholder_response(request)
