from __future__ import annotations

from typing import Any

from src.agents.state import AgentRuntimeInput
from src.internhunter.config.settings import settings


class _FakeAgentGraph:
    """Small test double for the LangChain agent graph."""

    def __init__(self, response: dict[str, Any]) -> None:
        """Store the canned response and all invocation calls."""
        self.response = response
        self.calls: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

    def invoke(self, payload: dict[str, Any], config: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        """Record payload and config separately and return the canned response."""
        self.calls.append((payload, config))
        return self.response


class _FakeProvider:
    """Provider seam used to keep runtime tests offline."""

    def build_model(self) -> str:
        """Return a placeholder model handle for the fake graph."""
        return "fake-model"


class _RecordingAgentFactory:
    """Test helper that records the arguments used to build the runtime graph."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> _FakeAgentGraph:
        self.calls.append(kwargs)
        return _FakeAgentGraph({"messages": [{"role": "assistant", "content": "Hello"}]})


class _FakeMemory:
    """Memory seam used to verify runtime session threading behavior."""

    def __init__(self) -> None:
        """Store session ids and appended messages for assertions."""
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


def test_build_agent_runtime_returns_runtime_object() -> None:
    """The runtime factory should return an invocable runtime wrapper."""
    from src.agents.runtime import build_agent_runtime

    runtime = build_agent_runtime(
        provider=_FakeProvider(),
        agent_factory=lambda **_: _FakeAgentGraph({"messages": [{"role": "assistant", "content": "Hello"}]}),
    )

    assert runtime is not None
    assert hasattr(runtime, "invoke")


def test_build_agent_runtime_loads_system_prompt_from_yaml(monkeypatch) -> None:
    """The runtime should use the YAML-backed agent prompt rather than a local prompt module."""
    from src.agents.runtime import build_agent_runtime

    factory = _RecordingAgentFactory()
    original_prompts = settings.prompts_yaml
    monkeypatch.setattr(
        settings,
        "prompts_yaml",
        {"prompts": {"agent_runtime_system": "YAML runtime prompt for tests."}},
    )

    try:
        build_agent_runtime(provider=_FakeProvider(), agent_factory=factory)
    finally:
        monkeypatch.setattr(settings, "prompts_yaml", original_prompts)

    assert factory.calls[0]["system_prompt"] == "YAML runtime prompt for tests."


def test_agent_runtime_invoke_returns_last_assistant_message() -> None:
    """Runtime invocation should map graph output into the typed result."""
    from src.agents.runtime import AgentRuntime

    monkeypatch.setattr("src.agents.runtime.build_langchain_tracing_config", lambda **_: {})
    monkeypatch.setattr("src.agents.runtime.get_current_trace_id_or_fallback", lambda config=None: "trace-plain-1")

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

    assert result.answer == "I can help you explore the job database safely."
    assert result.warnings == []
    assert result.trace_id == "trace-plain-1"
    assert graph.calls == [
        (
            {"messages": [{"role": "user", "content": "Hello"}]},
            None,
        )
    ]


def test_agent_runtime_passes_simple_langchain_tracing_config(monkeypatch) -> None:
    """Runtime invocation should pass Langfuse callbacks and metadata through config."""
    from src.agents.runtime import AgentRuntime

    graph = _FakeAgentGraph(
        {
            "messages": [
                {"role": "assistant", "content": "I can help you explore the job database safely."},
            ]
        }
    )
    memory = _FakeMemory()
    monkeypatch.setattr(
        "src.agents.runtime.build_langchain_tracing_config",
        lambda **_: {
            "callbacks": ["handler"],
            "metadata": {
                "langfuse_user_id": "user-1",
                "langfuse_session_id": "session-1",
            },
        },
    )
    monkeypatch.setattr("src.agents.runtime.get_current_trace_id_or_fallback", lambda config=None: "runtime-trace-1")
    runtime = AgentRuntime(agent=graph, memory=memory)

    result = runtime.invoke(AgentRuntimeInput(question="Hello", session_id="session-1", user_id="user-1"))

    assert result.answer == "I can help you explore the job database safely."
    assert result.trace_id == "runtime-trace-1"
    assert memory.session_ids == ["session-1"]
    assert memory.appended == [
        ("session-1", "user", "Hello"),
        ("session-1", "assistant", "I can help you explore the job database safely."),
    ]
    assert graph.calls == [
        (
            {"messages": [{"role": "user", "content": "Hello"}]},
            {
                "configurable": {"thread_id": "session-1"},
                "callbacks": ["handler"],
                "metadata": {
                    "langfuse_user_id": "user-1",
                    "langfuse_session_id": "session-1",
                },
            },
        )
    ]
