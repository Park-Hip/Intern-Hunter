from __future__ import annotations

from src.agents.guardrail import screen_question
from src.agents.runtime import build_agent_runtime
from src.agents.state import AgentRuntimeInput, AgentRuntimeOutput
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

_RUNTIME_CACHE: object | None = None
_RUNTIME_FACTORY: object | None = None


def _build_metadata(
    request: AgentAskRequest,
    trace_id: str = "stub-trace-id",
) -> AgentResponseMetadata:
    """Build response metadata while preserving the current public API shape."""
    return AgentResponseMetadata(
        limit_applied=False,
        execution_skipped=True,
        trace_id=trace_id,
        session_id=request.session_id,
        user_id=request.user_id,
    )


def _to_request_artifact(request: AgentAskRequest) -> AskRequestArtifact:
    """Convert the HTTP request into the internal guardrail input artifact."""
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
    """Build the typed refusal envelope returned before runtime execution."""
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
    """Return the current preview-only stub without invoking the runtime."""
    return AgentAskPreviewResponse(
        question=request.question,
        sql=AgentSQLPayload(validated_sql="-- preview stub; no SQL generated yet"),
        summary="Preview mode is wired. Real SQL preview is not implemented yet.",
        warnings=["Stub preview only. No SQL was executed."],
        metadata=_build_metadata(request),
    )


def _invoke_allowed_runtime(request: AgentAskRequest) -> AgentRuntimeOutput:
    """Invoke the Milestone 1 runtime for allowed non-preview requests."""
    runtime = _get_agent_runtime()
    return runtime.invoke(
        AgentRuntimeInput(
            question=request.question,
            session_id=request.session_id,
            user_id=request.user_id,
            preview_only=request.preview_only,
        )
    )


def _get_agent_runtime():
    """Return a cached runtime instance so short session memory survives API calls."""
    global _RUNTIME_CACHE, _RUNTIME_FACTORY

    current_factory = build_agent_runtime
    if _RUNTIME_CACHE is None or _RUNTIME_FACTORY is not current_factory:
        _RUNTIME_CACHE = current_factory()
        _RUNTIME_FACTORY = current_factory
    return _RUNTIME_CACHE


def _build_allowed_runtime_response(request: AgentAskRequest) -> AgentAskOkResponse:
    """Translate the runtime result into the existing typed API response."""
    runtime_output = _invoke_allowed_runtime(request)
    return AgentAskOkResponse(
        question=request.question,
        sql=AgentSQLPayload(),
        summary=runtime_output.summary,
        warnings=runtime_output.warnings,
        metadata=_build_metadata(request, trace_id=runtime_output.trace_id),
    )


def handle_agent_ask(
    request: AgentAskRequest,
) -> AgentAskOkResponse | AgentAskPreviewResponse | AgentAskRefusedResponse:
    """Handle the typed `/agent/ask` workflow with guardrail-first branching."""
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

    return _build_allowed_runtime_response(request)
