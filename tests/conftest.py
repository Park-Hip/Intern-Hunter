import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy as db
from sqlalchemy.orm import sessionmaker
import json
from src.internhunter.storage.models import Base
from unittest.mock import MagicMock

# --- Database Fixtures ---

@pytest.fixture(scope="function")
def engine():
    """Create an in-memory SQLite engine for tests."""
    engine = db.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    # Create all tables in the in-memory database
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture(scope="function")
def test_db_session(engine, monkeypatch):
    """Override the production SessionLocal with our test session."""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # We patch the `SessionLocal` class where it is used.
    monkeypatch.setattr("src.internhunter.storage.repositories.etl.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.internhunter.search.repository.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.internhunter.resume.repository.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.internhunter.resume.matching.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.internhunter.storage.session.SessionLocal", TestSessionLocal)
    
    session = TestSessionLocal()
    yield session
    session.close()

# --- LLM Mocks ---

@pytest.fixture
def mock_llm_response():
    """Returns a dummy structured JSON response from an LLM."""
    return json.dumps({
        "standardized_title": "Software Engineer Test",
        "job_level": "Mid",
        "is_internship": False,
        "description": "A test description",
        "requirement": "A test requirement",
        "benefit": "A test benefit",
        "cities": ["Ho Chi Minh", "Ha Noi"],
        "experience": 2.0,
        "min_gpa": 3.0,
        "english_requirement": "IELTS 6.0",
        "salary_min": 1000.0,
        "salary_max": 2000.0,
        "currency": "USD",
        "is_salary_negotiable": True,
        "tech_stack": ["Python", "Pytest"],
        "technical_competencies": ["Testing"],
        "domain_knowledge": ["Software Testing"]
    })

@pytest.fixture
def mock_gemini_client(monkeypatch, mock_llm_response):
    """Mocks the GeminiClient so we don't hit the real API during tests."""
    class MockClient:
        def __init__(self, *args, **kwargs):
            self.model = "gemini-2.5-flash-lite"
            self.client = MagicMock()
            
            # Setup the mocked response chain
            mock_resp = MagicMock()
            from src.core.models import LLMJobProcess
            import json
            mock_resp.parsed = LLMJobProcess(**json.loads(mock_llm_response))
            mock_resp.text = mock_llm_response
            self.client.models.generate_content.return_value = mock_resp

        def get_model(self):
            return self.client
            
    monkeypatch.setattr("src.internhunter.extraction.validator.GeminiClient", MockClient)
    monkeypatch.setattr("src.internhunter.llm.providers.GeminiClient", MockClient)
    return MockClient

