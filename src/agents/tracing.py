from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from src.internhunter.config.settings import settings


class AgentTracer(Protocol):
    """Protocol for runtime tracing implementations."""

    def start_trace(self, question: str) -> str:
        """Start a trace for one agent question and return its identifier."""

    def finish_trace(self, trace_id: str, status: str) -> None:
        """Finish a previously started trace."""


class NullAgentTracer:
    """Fail-open tracing implementation used when no backend is configured."""

    def start_trace(self, question: str) -> str:
        """Return a generated trace id without emitting remote telemetry."""
        return f"agent-trace-{uuid4()}"

    def finish_trace(self, trace_id: str, status: str) -> None:
        """Complete the trace without any side effects."""
        return None


class LangfuseAgentTracer:
    """Small Langfuse-backed tracer seam for Milestone 1 runtime telemetry."""

    def __init__(self, public_key: str, secret_key: str, host: str | None = None) -> None:
        """Build the real Langfuse client and keep trace handles by trace id."""
        from langfuse import Langfuse

        self.client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        self._trace_clients: dict[str, object] = {}

    def start_trace(self, question: str) -> str:
        """Create a real Langfuse trace and fall back to a local id on failure."""
        try:
            trace = self.client.trace(
                name="agent.ask",
                input={"question": question},
                metadata={"component": "internhunter-agent-runtime"},
            )
            trace_id = str(getattr(trace, "id", "")) or f"agent-trace-{uuid4()}"
            self._trace_clients[trace_id] = trace
            return trace_id
        except Exception:
            return f"agent-trace-{uuid4()}"

    def finish_trace(self, trace_id: str, status: str) -> None:
        """Update and flush best-effort without letting tracing failures escape."""
        trace = self._trace_clients.pop(trace_id, None)
        if trace is None:
            return None

        try:
            trace.update(output={"status": status})
            self.client.flush()
        except Exception:
            return None
        return None


def build_agent_tracer() -> AgentTracer:
    """Build the configured tracer and fall back to a null tracer when absent."""
    public_key = settings.LANGFUSE_PUBLIC_KEY
    secret_key = settings.LANGFUSE_SECRET_KEY
    host = settings.LANGFUSE_HOST

    if public_key and secret_key:
        return LangfuseAgentTracer(
            public_key=public_key.get_secret_value(),
            secret_key=secret_key.get_secret_value(),
            host=host,
        )

    return NullAgentTracer()
