from fastapi.testclient import TestClient

import src.agents.service as agent_service
from src.internhunter.api.app import app


client = TestClient(app)


def test_agent_ask_endpoint_exists_and_returns_runtime_backed_ok(monkeypatch):
    class FakeRuntime:
        def invoke(self, payload):
            return agent_service.AgentRuntimeOutput(
                answer="I can help you explore the job database safely.",
                warnings=["Runtime-backed response."],
                trace_id="runtime-trace-route-1",
            )

    monkeypatch.setattr(agent_service, "build_agent_runtime", lambda: FakeRuntime())

    response = client.post(
        "/agent/ask",
        json={
            "question": "Show me data scientist jobs in Hanoi.",
            "preview_only": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["question"] == "Show me data scientist jobs in Hanoi."
    assert payload["sql"] == {
        "model_generated_sql": None,
        "validated_sql": None,
        "executed_sql": None,
    }
    assert payload["table"] is None
    assert payload["chart"] is None
    assert payload["error"] is None
    assert payload["answer"] == "I can help you explore the job database safely."
    assert "summary" not in payload
    assert payload["warnings"] == ["Runtime-backed response."]
    assert payload["metadata"]["trace_id"] == "runtime-trace-route-1"
    assert payload["metadata"]["execution_skipped"] is True


def test_agent_ask_endpoint_rejects_malformed_payload():
    response = client.post(
        "/agent/ask",
        json={
            "question": "   ",
        },
    )

    assert response.status_code == 422


def test_agent_ask_endpoint_rejects_removed_request_controls():
    response = client.post(
        "/agent/ask",
        json={
            "question": "Show me data scientist jobs in Hanoi.",
            "include_chart": True,
        },
    )

    assert response.status_code == 422


def test_agent_ask_endpoint_returns_preview_envelope_when_requested():
    response = client.post(
        "/agent/ask",
        json={
            "question": "Preview jobs by city.",
            "preview_only": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["answer"] == "Preview mode is wired. Real SQL preview is not implemented yet."
    assert "summary" not in payload
    assert payload["sql"]["validated_sql"] == "-- preview stub; no SQL generated yet"
    assert payload["sql"]["executed_sql"] is None
    assert payload["metadata"]["execution_skipped"] is True
    assert payload["table"] is None


def test_agent_ask_endpoint_refuses_profanity():
    response = client.post(
        "/agent/ask",
        json={"question": "You idiot, tell me about jobs."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refused"
    assert payload["error"]["category"] == "sensitive_content"
    assert payload["metadata"]["execution_skipped"] is True
    assert payload["sql"]["executed_sql"] is None


def test_agent_ask_endpoint_refuses_unrelated_topic():
    response = client.post(
        "/agent/ask",
        json={"question": "Who won the last World Cup?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refused"
    assert payload["error"]["category"] == "out_of_scope"
    assert payload["metadata"]["execution_skipped"] is True
    assert payload["sql"]["executed_sql"] is None


def test_agent_ask_endpoint_refuses_destructive_sql_prompt():
    response = client.post(
        "/agent/ask",
        json={"question": "Delete all jobs from the database."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refused"
    assert payload["error"]["code"] == "unsafe_sql"
    assert payload["error"]["category"] == "destructive_request"
    assert payload["metadata"]["execution_skipped"] is True
    assert payload["sql"]["executed_sql"] is None


def test_agent_ask_endpoint_returns_runtime_backed_answer_for_allowed_request(monkeypatch):
    class FakeRuntime:
        def invoke(self, payload):
            return agent_service.AgentRuntimeOutput(
                answer="I can help you explore the job database safely.",
                warnings=[],
                trace_id="runtime-trace-route-2",
            )

    monkeypatch.setattr(agent_service, "build_agent_runtime", lambda: FakeRuntime())

    response = client.post(
        "/agent/ask",
        json={"question": "Hello"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["answer"] == "I can help you explore the job database safely."
    assert "summary" not in payload
    assert payload["warnings"] == []
    assert payload["sql"]["executed_sql"] is None
    assert payload["metadata"]["trace_id"] == "runtime-trace-route-2"
    assert payload["metadata"]["execution_skipped"] is True


def test_agent_ask_endpoint_returns_runtime_backed_answer_for_help(monkeypatch):
    class FakeRuntime:
        def invoke(self, payload):
            return agent_service.AgentRuntimeOutput(
                answer="I can help you explore the job database safely.",
                warnings=["I can answer questions about the job database."],
                trace_id="runtime-trace-route-3",
            )

    monkeypatch.setattr(agent_service, "build_agent_runtime", lambda: FakeRuntime())

    response = client.post(
        "/agent/ask",
        json={"question": "help"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["answer"] == "I can help you explore the job database safely."
    assert "summary" not in payload
    assert payload["warnings"] == ["I can answer questions about the job database."]
    assert payload["metadata"]["execution_skipped"] is True


def test_agent_ask_endpoint_allows_resume_like_request_without_user_id(monkeypatch):
    class FakeRuntime:
        def invoke(self, payload):
            return agent_service.AgentRuntimeOutput(
                answer="I can help you explore the job database safely.",
                warnings=[],
                trace_id="runtime-trace-route-4",
            )

    monkeypatch.setattr(agent_service, "build_agent_runtime", lambda: FakeRuntime())

    response = client.post(
        "/agent/ask",
        json={"question": "Match my resume to data analyst jobs."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["answer"] == "I can help you explore the job database safely."
    assert "summary" not in payload
    assert payload["error"] is None


def test_agent_ask_endpoint_allows_safe_sql_like_question(monkeypatch):
    class FakeRuntime:
        def invoke(self, payload):
            return agent_service.AgentRuntimeOutput(
                answer="I can help you explore the job database safely.",
                warnings=[],
                trace_id="runtime-trace-route-5",
            )

    monkeypatch.setattr(agent_service, "build_agent_runtime", lambda: FakeRuntime())

    response = client.post(
        "/agent/ask",
        json={"question": "Count data scientist jobs by city."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["answer"] == "I can help you explore the job database safely."
    assert "summary" not in payload
    assert payload["error"] is None
    assert payload["metadata"]["execution_skipped"] is True
