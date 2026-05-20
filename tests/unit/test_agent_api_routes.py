from fastapi.testclient import TestClient

from src.internhunter.api.app import app


client = TestClient(app)


def test_agent_ask_endpoint_exists_and_returns_stub_ok():
    response = client.post(
        "/agent/ask",
        json={
            "question": "Show me data scientist jobs in Hanoi.",
            "preview_only": False,
            "include_summary": True,
            "include_chart": False,
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
    assert payload["metadata"]["execution_skipped"] is True


def test_agent_ask_endpoint_rejects_malformed_payload():
    response = client.post(
        "/agent/ask",
        json={
            "question": "   ",
            "limit": 0,
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


def test_agent_ask_endpoint_refuses_unrelated_topic():
    response = client.post(
        "/agent/ask",
        json={"question": "Who won the last World Cup?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "refused"
    assert payload["error"]["category"] == "out_of_scope"


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


def test_agent_ask_endpoint_returns_generic_ok_placeholder_for_allowed_request():
    response = client.post(
        "/agent/ask",
        json={"question": "Hello"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"] == "Agent endpoint is guardrailed. Real orchestration is not implemented yet."
    assert payload["warnings"] == ["Stub response only. No SQL was generated or executed."]
    assert payload["sql"]["executed_sql"] is None
    assert payload["metadata"]["execution_skipped"] is True


def test_agent_ask_endpoint_returns_generic_ok_placeholder_for_help():
    response = client.post(
        "/agent/ask",
        json={"question": "help"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"] == "Agent endpoint is guardrailed. Real orchestration is not implemented yet."
    assert payload["warnings"] == ["Stub response only. No SQL was generated or executed."]
    assert payload["metadata"]["execution_skipped"] is True


def test_agent_ask_endpoint_allows_resume_like_request_without_user_id():
    response = client.post(
        "/agent/ask",
        json={"question": "Match my resume to data analyst jobs."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["summary"] == "Agent endpoint is guardrailed. Real orchestration is not implemented yet."
    assert payload["error"] is None


def test_agent_ask_endpoint_allows_safe_sql_like_question():
    response = client.post(
        "/agent/ask",
        json={"question": "Count data scientist jobs by city."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["error"] is None
    assert payload["metadata"]["execution_skipped"] is True
