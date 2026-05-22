from __future__ import annotations

import sys
import types

from pydantic import SecretStr

from src.agents.tracing import (
    build_langchain_tracing_config,
    get_current_trace_id_or_fallback,
    trace_guardrail_decision,
)


def test_build_langchain_tracing_config_returns_callbacks_and_metadata(monkeypatch) -> None:
    """The tracing helper should return LangChain callbacks plus safe Langfuse metadata."""

    class _FakeLangfuse:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _FakeCallbackHandler:
        def __init__(self, public_key=None) -> None:
            self.public_key = public_key

    monkeypatch.setitem(sys.modules, "langfuse", types.SimpleNamespace(Langfuse=_FakeLangfuse))
    monkeypatch.setitem(
        sys.modules,
        "langfuse.langchain",
        types.SimpleNamespace(CallbackHandler=_FakeCallbackHandler),
    )
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

    config = build_langchain_tracing_config(user_id="user-1", session_id="session-1")

    assert len(config["callbacks"]) == 1
    assert isinstance(config["callbacks"][0], _FakeCallbackHandler)
    assert config["callbacks"][0].public_key == "public-test"
    assert config["metadata"] == {
        "langfuse_user_id": "user-1",
        "langfuse_session_id": "session-1",
    }


def test_build_langchain_tracing_config_returns_empty_when_langfuse_is_unconfigured(monkeypatch) -> None:
    """The tracing helper should fail open when Langfuse credentials are missing."""
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

    assert build_langchain_tracing_config(user_id=None, session_id=None) == {}


def test_trace_guardrail_decision_records_one_guardrail_observation(monkeypatch) -> None:
    """The guardrail helper should emit one Langfuse observation when configured."""

    class _FakeObservation:
        def __init__(self) -> None:
            self.update_trace_calls: list[dict[str, object]] = []
            self.update_calls: list[dict[str, object]] = []
            self.end_calls = 0

        def update_trace(self, **kwargs) -> None:
            self.update_trace_calls.append(kwargs)

        def update(self, **kwargs) -> None:
            self.update_calls.append(kwargs)

        def end(self) -> None:
            self.end_calls += 1

    class _FakeContextManager:
        def __init__(self, observation) -> None:
            self.observation = observation

        def __enter__(self):
            return self.observation

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _FakeClient:
        instances: list["_FakeClient"] = []

        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.calls: list[dict[str, object]] = []
            self.observation = _FakeObservation()
            self.flush_calls = 0
            _FakeClient.instances.append(self)

        def start_as_current_observation(self, **kwargs):
            self.calls.append(kwargs)
            return _FakeContextManager(self.observation)

        def flush(self) -> None:
            self.flush_calls += 1

        def get_current_trace_id(self) -> str:
            return "guardrail-trace-1"

    monkeypatch.setitem(sys.modules, "langfuse", types.SimpleNamespace(Langfuse=_FakeClient))
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

    trace_id = trace_guardrail_decision(
        question="Drop the clean_jobs table.",
        allowed=False,
        refusal_category="destructive_request",
        refusal_code="unsafe_sql",
        session_id="session-1",
        user_id="user-1",
    )

    client = _FakeClient.instances[0]
    assert trace_id == "guardrail-trace-1"
    assert client.calls == [
        {
            "name": "agent.guardrail",
            "as_type": "guardrail",
            "input": {"question": "Drop the clean_jobs table."},
            "metadata": {
                "allowed": False,
                "category": "destructive_request",
                "code": "unsafe_sql",
            },
        }
    ]
    assert client.observation.update_trace_calls == [{"session_id": "session-1", "user_id": "user-1"}]
    assert client.observation.update_calls == [
        {
            "output": {
                "allowed": False,
                "category": "destructive_request",
                "code": "unsafe_sql",
            }
        }
    ]
    assert client.observation.end_calls == 1
    assert client.flush_calls == 1


def test_get_current_trace_id_or_fallback_prefers_callback_handler_state() -> None:
    """The runtime should prefer the callback handler trace id after invocation."""

    class _FakeCallbackHandler:
        last_trace_id = "runtime-trace-1"

    trace_id = get_current_trace_id_or_fallback({"callbacks": [_FakeCallbackHandler()]})

    assert trace_id == "runtime-trace-1"
