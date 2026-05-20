from __future__ import annotations

from typing import Any

from src.agents.state import AgentRuntimeInput


class _FakeAgentGraph:
    """Small test double for the LangChain agent graph."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record payloads and return the canned response."""
        self.calls.append(payload)
        return self.response


class _FakeProvider:
    """Provider seam used to keep the runtime test offline."""

    def build_model(self) -> str:
        """Return a placeholder model handle for the fake graph."""
        return "fake-model"


class _FakeMemory:
    """Memory seam used to verify runtime session threading behavior."""

    def __init__(self) -> None:
        self.session_ids: list[str | None] = []
        self.appended: list[tuple[str, str, str]] = []

    def get(self, session_id: str) -> list[dict[str, str]]:
        """Return an empty history for the session under test."""
        return []

    def build_invocation_config(self, session_id: str | None) -> dict[str, Any]:
        """Record the session and return a LangGraph-style thread config."""
        self.session_ids.append(session_id)
        if session_id is None:
            return {}
        return {"configurable": {"thread_id": session_id}}

    def append(self, session_id: str, role: str, content: str) -> None:
        """Record messages written back into the memory seam."""
        self.appended.append((session_id, role, content))


class _FakeTracer:
    """Tracer seam used to keep runtime tests deterministic."""

    def __init__(self) -> None:
        self.started_with: list[str] = []
        self.finished_with: list[tuple[str, str]] = []

    def start_trace(self, question: str) -> str:
        """Record the question and return a stable trace identifier."""
        self.started_with.append(question)
        return "trace-123"

    def finish_trace(self, trace_id: str, status: str) -> None:
        """Record trace completion details."""
        self.finished_with.append((trace_id, status))


def test_build_agent_runtime_returns_runtime_object() -> None:
    """The runtime factory should return an invocable runtime wrapper."""
    from src.agents.runtime import build_agent_runtime

    runtime = build_agent_runtime(
        provider=_FakeProvider(),
        agent_factory=lambda **_: _FakeAgentGraph({"messages": [{"role": "assistant", "content": "Hello"}]}),
    )

    assert runtime is not None
    assert hasattr(runtime, "invoke")


def test_agent_runtime_invoke_returns_last_assistant_message() -> None:
    """Runtime invocation should map graph output into the typed result."""
    from src.agents.runtime import AgentRuntime

    graph = _FakeAgentGraph(
        {
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "I can help you explore the job database safely."},
            ]
        }
    )
    runtime = AgentRuntime(agent=graph)

    result = runtime.invoke(AgentRuntimeInput(question="Hello"))

    assert result.summary == "I can help you explore the job database safely."
    assert result.warnings == []
    assert result.trace_id
    assert graph.calls == [
        {
            "messages": [{"role": "user", "content": "Hello"}],
        }
    ]


def test_agent_runtime_invoke_threads_memory_and_tracing() -> None:
    """Runtime invocation should use injected seams for session memory and tracing."""
    from src.agents.runtime import AgentRuntime

    graph = _FakeAgentGraph(
        {
            "messages": [
                {"role": "assistant", "content": "I can help you explore the job database safely."},
            ]
        }
    )
    memory = _FakeMemory()
    tracer = _FakeTracer()
    runtime = AgentRuntime(agent=graph, memory=memory, tracer=tracer)

    result = runtime.invoke(AgentRuntimeInput(question="Hello", session_id="session-1"))

    assert result.trace_id == "trace-123"
    assert memory.session_ids == ["session-1"]
    assert memory.appended == [
        ("session-1", "user", "Hello"),
        ("session-1", "assistant", "I can help you explore the job database safely."),
    ]
    assert tracer.started_with == ["Hello"]
    assert tracer.finished_with == [("trace-123", "ok")]
    assert graph.calls == [
        {
            "messages": [
                {"role": "user", "content": "Hello"},
            ],
            "config": {"configurable": {"thread_id": "session-1"}},
        }
    ]
