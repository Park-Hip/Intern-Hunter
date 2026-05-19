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
