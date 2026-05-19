from fastapi.testclient import TestClient

from src.internhunter.api.app import app
import src.internhunter.api.routes.demo_routes as demo_routes
from src.internhunter.storage.models import CleanJobDB, RawJobDB


client = TestClient(app)


def test_health_endpoint_returns_ok(monkeypatch):
    monkeypatch.setattr(demo_routes, "_check_db_connection", lambda: True)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "search": "ready"}


def test_jobs_search_endpoint_returns_mocked_results(monkeypatch):
    monkeypatch.setattr(
        demo_routes.search_repo,
        "search_jobs_by_criteria",
        lambda **kwargs: [
            {
                "title": "Data Scientist",
                "company": "TopCV",
                "cities": ["Hanoi"],
                "url": "https://example.com/job/1",
                "salary_range": "10000000 - 20000000 VND",
            }
        ],
    )

    response = client.get("/jobs/search", params={"query": "data scientist", "limit": 5})

    assert response.status_code == 200
    assert response.json() == [
        {
            "title": "Data Scientist",
            "company": "TopCV",
            "cities": ["Hanoi"],
            "url": "https://example.com/job/1",
            "salary_range": "10000000 - 20000000 VND",
        }
    ]


def test_jobs_search_endpoint_semantic_mode_uses_embedding_and_similarity_search(monkeypatch):
    captured = {}

    monkeypatch.setattr(demo_routes.embedder, "generate_embedding", lambda query: [0.1, 0.2, 0.3])

    def fake_similarity_search(embedding, limit=5):
        captured["embedding"] = embedding
        captured["limit"] = limit
        return [
            {
                "title": "Semantic Match",
                "company": "TopCV",
                "cities": ["Hanoi"],
                "url": "https://example.com/job/semantic",
                "match_score": 0.93,
            }
        ]

    monkeypatch.setattr(demo_routes.search_repo, "search_jobs_by_similarity", fake_similarity_search)

    response = client.get(
        "/jobs/search",
        params={"query": "python machine learning", "limit": 5, "mode": "semantic"},
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "title": "Semantic Match",
            "company": "TopCV",
            "cities": ["Hanoi"],
            "url": "https://example.com/job/semantic",
            "match_score": 0.93,
        }
    ]
    assert captured["embedding"] == [0.1, 0.2, 0.3]
    assert captured["limit"] == 5


def test_jobs_search_endpoint_handles_empty_results(monkeypatch):
    monkeypatch.setattr(demo_routes.search_repo, "search_jobs_by_criteria", lambda **kwargs: [])
    monkeypatch.setattr(demo_routes, "_get_recent_clean_jobs", lambda limit: [])

    response = client.get("/jobs/search", params={"query": "data scientist", "limit": 5})

    assert response.status_code == 200
    assert response.json() == []


def test_jobs_search_endpoint_invalid_mode_returns_400():
    response = client.get("/jobs/search", params={"query": "data scientist", "limit": 5, "mode": "vector"})

    assert response.status_code == 400
    assert response.json()["detail"] == "mode must be either 'criteria' or 'semantic'."


def test_jobs_search_endpoint_semantic_embedding_failure_returns_500(monkeypatch):
    def boom(query):
        raise RuntimeError("gemini offline")

    monkeypatch.setattr(demo_routes.embedder, "generate_embedding", boom)

    response = client.get(
        "/jobs/search",
        params={"query": "python machine learning", "limit": 5, "mode": "semantic"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to generate query embedding."


def test_resume_match_endpoint_rejects_empty_resume_text():
    response = client.post(
        "/resume/match",
        json={"user_id": "demo-user", "resume_text": "   ", "limit": 5},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "resume_text cannot be empty."


def test_resume_match_endpoint_returns_mocked_matches(monkeypatch):
    monkeypatch.setattr(
        demo_routes,
        "execute_upload_resume",
        lambda user_id, resume_text: "Resume successfully uploaded and vectorized. You can now ask me to match jobs based on your profile!",
    )
    monkeypatch.setattr(
        demo_routes,
        "execute_match_resume",
        lambda user_id, limit=5: [
            {
                "title": "Machine Learning Engineer",
                "company": "TopCV",
                "cities": ["Ho Chi Minh City"],
                "url": "https://example.com/job/2",
                "match_score": 0.97,
            }
        ],
    )

    response = client.post(
        "/resume/match",
        json={
            "user_id": "demo-user",
            "resume_text": "Python data scientist with machine learning experience.",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "title": "Machine Learning Engineer",
            "company": "TopCV",
            "cities": ["Ho Chi Minh City"],
            "url": "https://example.com/job/2",
            "match_score": 0.97,
        }
    ]


def test_map_job_row_prefers_clean_job_company():
    raw_job = RawJobDB(company="Raw Company", url="https://example.com/raw")
    clean_job = CleanJobDB(
        standardized_title="Data Scientist",
        company="Clean Company",
        cities=["Hanoi"],
        salary_min=10000000,
        salary_max=20000000,
        currency="VND",
    )
    clean_job.raw_job = raw_job

    payload = demo_routes._map_job_row(clean_job)

    assert payload["company"] == "Clean Company"
    assert payload["url"] == "https://example.com/raw"
