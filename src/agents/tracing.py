from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.internhunter.config.settings import settings


def build_local_trace_id() -> str:
    """Create a local fallback trace identifier when Langfuse is unavailable."""
    return f"agent-trace-{uuid4()}"


def build_langchain_tracing_config(
    *,
    user_id: str | None,
    session_id: str | None,
) -> dict[str, Any]:
    """Build LangChain callback config for one traced agent invocation."""
    credentials = _langfuse_credentials()
    if credentials is None:
        return {}

    public_key, secret_key, host = credentials

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

        Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        handler = CallbackHandler(public_key=public_key)
    except Exception:
        return {}

    metadata = {
        "langfuse_user_id": user_id,
        "langfuse_session_id": session_id,
    }
    filtered_metadata = {key: value for key, value in metadata.items() if value is not None}
    config: dict[str, Any] = {"callbacks": [handler]}
    if filtered_metadata:
        config["metadata"] = filtered_metadata
    return config


def trace_guardrail_decision(
    *,
    question: str,
    allowed: bool,
    refusal_category: str | None = None,
    refusal_code: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> str:
    """Trace one guardrail decision and return the best available trace identifier."""
    credentials = _langfuse_credentials()
    if credentials is None:
        return build_local_trace_id()

    public_key, secret_key, host = credentials
    metadata: dict[str, Any] = {"allowed": allowed}
    output: dict[str, Any] = {"allowed": allowed}
    if refusal_category is not None:
        metadata["category"] = refusal_category
        output["category"] = refusal_category
    if refusal_code is not None:
        metadata["code"] = refusal_code
        output["code"] = refusal_code

    try:
        from langfuse import Langfuse

        client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        with client.start_as_current_observation(
            name="agent.guardrail",
            as_type="guardrail",
            input={"question": question},
            metadata=metadata,
        ) as observation:
            if hasattr(observation, "update_trace"):
                observation.update_trace(session_id=session_id, user_id=user_id)
            observation.end(output=output)
        client.flush()
        return client.get_current_trace_id() or build_local_trace_id()
    except Exception:
        return build_local_trace_id()


def get_current_trace_id_or_fallback(config: dict[str, Any] | None = None) -> str:
    """Return the active Langfuse trace id, or a local fallback when unavailable."""
    if config:
        for callback in config.get("callbacks", []):
            trace_id = getattr(callback, "last_trace_id", None)
            if isinstance(trace_id, str) and trace_id:
                return trace_id

    credentials = _langfuse_credentials()
    if credentials is None:
        return build_local_trace_id()

    public_key, secret_key, host = credentials
    try:
        from langfuse import Langfuse

        client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        return client.get_current_trace_id() or build_local_trace_id()
    except Exception:
        return build_local_trace_id()


def _langfuse_credentials() -> tuple[str, str, str | None] | None:
    """Read configured Langfuse credentials from typed settings."""
    public_key = settings.LANGFUSE_PUBLIC_KEY
    secret_key = settings.LANGFUSE_SECRET_KEY
    host = settings.LANGFUSE_HOST
    if not public_key or not secret_key:
        return None
    return public_key.get_secret_value(), secret_key.get_secret_value(), host
