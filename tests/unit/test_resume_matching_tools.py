import pytest

import src.internhunter.resume.matching as tools
from src.internhunter.storage.models import CleanJobDB, RawJobDB


def test_is_missing_embedding_handles_none_and_empty():
    assert tools.is_missing_embedding(None) is True
    assert tools.is_missing_embedding([]) is True
    assert tools.is_missing_embedding(()) is True


def test_extract_known_skills_is_case_insensitive():
    text = (
        "PYTHON, Sql, machine learning, Deep Learning, NLP, Computer Vision, Pandas, NumPy, "
        "scikit learn, PyTorch, TensorFlow, FastAPI, Flask, Docker, Git, AWS, Azure, "
        "Data Visualization, Statistics, MLOps, LangChain, Embeddings"
    )

    skills = tools.extract_known_skills(text)

    assert skills == {
        "python",
        "sql",
        "machine learning",
        "deep learning",
        "nlp",
        "computer vision",
        "pandas",
        "numpy",
        "scikit-learn",
        "pytorch",
        "tensorflow",
        "fastapi",
        "flask",
        "docker",
        "git",
        "aws",
        "azure",
        "data visualization",
        "statistics",
        "mlops",
        "langchain",
        "embeddings",
    }


def test_build_job_explanation_returns_deterministic_skill_fields():
    resume_text = "Python SQL machine learning FastAPI Docker Azure"
    job = {
        "title": "Data Scientist",
        "level": "Mid",
        "company": "TopCV",
        "cities": ["Hanoi"],
        "description": "Looking for python and sql skills. Machine learning experience is a plus.",
        "requirement": "FastAPI and Docker preferred",
        "tech_stack": ["Python", "Docker"],
        "technical_competencies": ["Build APIs"],
        "domain_knowledge": ["Machine Learning"],
    }

    explanation = tools.build_job_explanation(resume_text, job)

    assert explanation["matched_skills"] == ["python", "sql", "machine learning", "fastapi", "docker"]
    assert explanation["unmatched_resume_skills"] == ["azure"]
    assert explanation["reason"] == "Strong overlap on Python, SQL, and machine learning."


def test_build_job_explanation_returns_minimal_reason_for_vague_resume():
    explanation = tools.build_job_explanation(
        "Experienced professional with strong communication and leadership.",
        {
            "title": "Generalist Role",
            "company": "TopCV",
            "cities": ["Remote"],
            "description": "We value communication and collaboration.",
        },
    )

    assert explanation["matched_skills"] == []
    assert explanation["unmatched_resume_skills"] == []
    assert explanation["reason"] == "Resume text did not contain recognized skills from the current keyword list."


def test_build_job_explanation_uses_semantic_fallback_reason_when_no_skill_overlap():
    explanation = tools.build_job_explanation(
        "Python SQL FastAPI",
        {
            "title": "Business Analyst",
            "company": "TopCV",
            "cities": ["Remote"],
            "match_score": 0.91,
            "description": "Stakeholder communication and reporting.",
        },
    )

    assert explanation["matched_skills"] == []
    assert explanation["unmatched_resume_skills"] == ["python", "sql", "fastapi"]
    assert explanation["reason"] == "Matched primarily by semantic similarity; no explicit skill overlap found."


def test_execute_match_resume_accepts_list_embedding(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        tools.profile_repo,
        "get_user_profile",
        lambda user_id: {
            "user_id": user_id,
            "resume_text": "Python SQL machine learning FastAPI Docker Azure",
            "resume_embedding": [0.1, 0.2, 0.3],
        },
    )

    def fake_search_jobs_by_similarity(embedding, limit=5):
        captured["embedding"] = embedding
        captured["limit"] = limit
        return [
            {
                "title": "Data Scientist",
                "level": "Mid",
                "company": "TopCV",
                "cities": ["Hanoi"],
                "url": "https://example.com/job/1",
                "match_score": 0.99,
                "description": "Python and SQL with machine learning.",
                "requirement": "FastAPI and Docker",
                "tech_stack": ["Python", "Docker"],
                "technical_competencies": ["Build APIs"],
                "domain_knowledge": ["Machine Learning"],
            }
        ]

    monkeypatch.setattr(tools.search_repo, "search_jobs_by_similarity", fake_search_jobs_by_similarity)
    monkeypatch.setattr(tools, "_fetch_job_context_by_url", lambda url: {})

    results = tools.execute_match_resume("user-list", limit=7)

    assert results == [
        {
            "title": "Data Scientist",
            "level": "Mid",
            "company": "TopCV",
            "cities": ["Hanoi"],
            "url": "https://example.com/job/1",
            "match_score": 0.99,
            "description": "Python and SQL with machine learning.",
            "requirement": "FastAPI and Docker",
            "tech_stack": ["Python", "Docker"],
            "technical_competencies": ["Build APIs"],
            "domain_knowledge": ["Machine Learning"],
            "matched_skills": ["python", "sql", "machine learning", "fastapi", "docker"],
            "unmatched_resume_skills": ["azure"],
            "reason": "Strong overlap on Python, SQL, and machine learning.",
        }
    ]
    assert captured["embedding"] == [0.1, 0.2, 0.3]
    assert captured["limit"] == 7


def test_execute_match_resume_accepts_numpy_embedding(monkeypatch):
    np = pytest.importorskip("numpy")
    captured = {}

    monkeypatch.setattr(
        tools.profile_repo,
        "get_user_profile",
        lambda user_id: {
            "user_id": user_id,
            "resume_text": "Python machine learning statistics",
            "resume_embedding": np.array([0.1, 0.2, 0.3]),
        },
    )

    def fake_search_jobs_by_similarity(embedding, limit=5):
        captured["embedding"] = embedding
        captured["limit"] = limit
        return [
            {
                "title": "Machine Learning Engineer",
                "level": "Senior",
                "company": "TopCV",
                "cities": ["Ho Chi Minh City"],
                "url": "https://example.com/job/2",
                "match_score": 0.95,
                "description": "Python and machine learning with statistics.",
                "tech_stack": ["Python"],
                "technical_competencies": ["Model training"],
                "domain_knowledge": ["Machine Learning"],
            }
        ]

    monkeypatch.setattr(tools.search_repo, "search_jobs_by_similarity", fake_search_jobs_by_similarity)
    monkeypatch.setattr(tools, "_fetch_job_context_by_url", lambda url: {})

    results = tools.execute_match_resume("user-np", limit=3)

    assert results == [
        {
            "title": "Machine Learning Engineer",
            "level": "Senior",
            "company": "TopCV",
            "cities": ["Ho Chi Minh City"],
            "url": "https://example.com/job/2",
            "match_score": 0.95,
            "description": "Python and machine learning with statistics.",
            "tech_stack": ["Python"],
            "technical_competencies": ["Model training"],
            "domain_knowledge": ["Machine Learning"],
            "matched_skills": ["python", "machine learning", "statistics"],
            "unmatched_resume_skills": [],
            "reason": "Strong overlap on Python, machine learning, and statistics.",
        }
    ]
    assert captured["limit"] == 3
    assert np.array_equal(captured["embedding"], np.array([0.1, 0.2, 0.3]))


def test_execute_match_resume_returns_error_for_missing_embedding(monkeypatch):
    monkeypatch.setattr(
        tools.profile_repo,
        "get_user_profile",
        lambda user_id: {"user_id": user_id, "resume_embedding": None},
    )

    results = tools.execute_match_resume("user-missing", limit=5)

    assert results == [{"error": "No resume found for this user. Please upload a resume first."}]


def test_fetch_job_context_by_url_prefers_clean_job_company(test_db_session):
    raw_job = RawJobDB(
        url="https://example.com/job/company-context",
        title="Raw Title",
        company="Raw Company",
        location="Hanoi",
        full_json_dump={"foo": "bar"},
        status="pending",
    )
    test_db_session.add(raw_job)
    test_db_session.flush()
    test_db_session.add(
        CleanJobDB(
            raw_job_id=raw_job.id,
            standardized_title="Clean Title",
            company="Clean Company",
            job_level="Mid",
            is_internship=False,
            description="desc",
            requirement="req",
            benefit="benefit",
            cities=["Hanoi"],
            tech_stack=["Python"],
            technical_competencies=["Modeling"],
            domain_knowledge=["ML"],
        )
    )
    test_db_session.commit()

    context = tools._fetch_job_context_by_url("https://example.com/job/company-context")

    assert context["company"] == "Clean Company"
    assert context["title"] == "Clean Title"
