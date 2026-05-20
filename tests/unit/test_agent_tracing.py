from __future__ import annotations

import sys
import types

from pydantic import SecretStr

from src.agents.tracing import LangfuseAgentTracer, NullAgentTracer, build_agent_tracer


def test_null_tracer_returns_trace_id_without_side_effects() -> None:
    """The null tracer should still mint a usable trace identifier."""
    tracer = NullAgentTracer()

    trace_id = tracer.start_trace("What can you do?")

    assert isinstance(trace_id, str)
    assert trace_id


def test_null_tracer_finish_trace_is_a_no_op() -> None:
    """Finishing a trace should not raise when tracing is unconfigured."""
    tracer = NullAgentTracer()

    trace_id = tracer.start_trace("What can you do?")

    assert tracer.finish_trace(trace_id, "ok") is None


def test_build_agent_tracer_falls_back_to_null_when_unconfigured(monkeypatch) -> None:
    """The tracing factory should fail open when no backend config is present."""
    monkeypatch.setattr(
        "src.agents.tracing.settings",
        type(
            "_FakeSettings",
            (),
            {
                "LANGFUSE_PUBLIC_KEY": None,
                "LANGFUSE_SECRET_KEY": None,
                "LANGFUSE_HOST": None,
            },
        )(),
    )

    tracer = build_agent_tracer()

    assert isinstance(tracer, NullAgentTracer)


def test_build_agent_tracer_returns_langfuse_when_configured(monkeypatch) -> None:
    """The tracing factory should build the Langfuse-backed tracer from loaded settings."""
    class _FakeLangfuse:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def trace(self, **kwargs):
            return types.SimpleNamespace(id="trace-1", update=lambda **_: None)

        def flush(self) -> None:
            return None

    monkeypatch.setitem(sys.modules, "langfuse", types.SimpleNamespace(Langfuse=_FakeLangfuse))
    monkeypatch.setattr(
        "src.agents.tracing.settings",
        type(
            "_FakeSettings",
            (),
            {
                "LANGFUSE_PUBLIC_KEY": SecretStr("public-test"),
                "LANGFUSE_SECRET_KEY": SecretStr("secret-test"),
                "LANGFUSE_HOST": "https://langfuse.example",
            },
        )(),
    )

    tracer = build_agent_tracer()

    assert isinstance(tracer, LangfuseAgentTracer)


def test_build_agent_tracer_reads_langfuse_keys_from_loaded_settings(monkeypatch) -> None:
    """The tracing factory should honor Langfuse values loaded from the app settings layer."""
    class _FakeLangfuse:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        def trace(self, **kwargs):
            return types.SimpleNamespace(id="trace-2", update=lambda **_: None)

        def flush(self) -> None:
            return None

    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.setitem(sys.modules, "langfuse", types.SimpleNamespace(Langfuse=_FakeLangfuse))
    monkeypatch.setattr(
        "src.agents.tracing.settings",
        type(
            "_FakeSettings",
            (),
            {
                "LANGFUSE_PUBLIC_KEY": SecretStr("public-from-settings"),
                "LANGFUSE_SECRET_KEY": SecretStr("secret-from-settings"),
                "LANGFUSE_HOST": "https://settings-host.example",
            },
        )(),
    )

    tracer = build_agent_tracer()

    assert isinstance(tracer, LangfuseAgentTracer)
def test_langfuse_tracer_start_trace_uses_real_client_methods(monkeypatch) -> None:
    """Starting a trace should call the Langfuse client and return the created trace id."""

    class _FakeTraceClient:
        def __init__(self, trace_id: str) -> None:
            self.id = trace_id
            self.update_calls: list[dict[str, object]] = []

        def update(self, **kwargs) -> "_FakeTraceClient":
            self.update_calls.append(kwargs)
            return self

    class _FakeLangfuse:
        instances: list["_FakeLangfuse"] = []

        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.trace_calls: list[dict[str, object]] = []
            self.flush_calls = 0
            self.trace_client = _FakeTraceClient("trace-real-1")
            _FakeLangfuse.instances.append(self)

        def trace(self, **kwargs) -> _FakeTraceClient:
            self.trace_calls.append(kwargs)
            return self.trace_client

        def flush(self) -> None:
            self.flush_calls += 1

    monkeypatch.setitem(sys.modules, "langfuse", types.SimpleNamespace(Langfuse=_FakeLangfuse))

    tracer = LangfuseAgentTracer(
        public_key="public-test",
        secret_key="secret-test",
        host="https://langfuse.example",
    )

    trace_id = tracer.start_trace("What can you do?")
    client = _FakeLangfuse.instances[0]

    assert trace_id == "trace-real-1"
    assert client.kwargs["public_key"] == "public-test"
    assert client.kwargs["secret_key"] == "secret-test"
    assert client.kwargs["host"] == "https://langfuse.example"
    assert client.trace_calls == [
        {
            "name": "agent.ask",
            "input": {"question": "What can you do?"},
            "metadata": {"component": "internhunter-agent-runtime"},
        }
    ]


def test_langfuse_tracer_finish_trace_updates_and_flushes(monkeypatch) -> None:
    """Finishing a trace should update the trace and flush best-effort."""

    class _FakeTraceClient:
        def __init__(self, trace_id: str) -> None:
            self.id = trace_id
            self.update_calls: list[dict[str, object]] = []

        def update(self, **kwargs) -> "_FakeTraceClient":
            self.update_calls.append(kwargs)
            return self

    class _FakeLangfuse:
        instances: list["_FakeLangfuse"] = []

        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.trace_client = _FakeTraceClient("trace-real-2")
            self.flush_calls = 0
            _FakeLangfuse.instances.append(self)

        def trace(self, **kwargs) -> _FakeTraceClient:
            return self.trace_client

        def flush(self) -> None:
            self.flush_calls += 1

    monkeypatch.setitem(sys.modules, "langfuse", types.SimpleNamespace(Langfuse=_FakeLangfuse))

    tracer = LangfuseAgentTracer(public_key="public-test", secret_key="secret-test")
    trace_id = tracer.start_trace("What can you do?")

    assert trace_id == "trace-real-2"
    assert tracer.finish_trace(trace_id, "ok") is None

    client = _FakeLangfuse.instances[0]
    assert client.trace_client.update_calls == [{"output": {"status": "ok"}}]
    assert client.flush_calls == 1
