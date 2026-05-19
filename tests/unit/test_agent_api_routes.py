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
