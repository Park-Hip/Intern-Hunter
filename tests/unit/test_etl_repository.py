import pytest
from src.internhunter.storage.repositories.etl import ETLRepository
from src.internhunter.storage.models import RawJobDB, PipelineRunDB
from src.core.models import ProcessedJob

@pytest.fixture
def repo():
    return ETLRepository()

def test_save_raw_job(test_db_session, repo):
    job_data = {
        "url": "https://example.com/job/1",
        "title": "Software Engineer",
        "company": "Tech Corp",
        "location": "Remote",
        "full_json_dump": {"foo": "bar"},
        "status": "pending"
    }
    
    # Act
    success = repo.save_raw_job(job_data)
    
    # Assert
    assert success is True
    saved_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/1").first()
    assert saved_job is not None
    assert saved_job.title == "Software Engineer"
    assert saved_job.status == "pending"

def test_save_raw_job_duplicate_url(test_db_session, repo):
    job_data = {"url": "https://example.com/job/1", "title": "First"}
    repo.save_raw_job(job_data)
    
    # Try saving duplicate
    job_data_dup = {"url": "https://example.com/job/1", "title": "Second"}
    success = repo.save_raw_job(job_data_dup)
    
    assert success is True
    count = test_db_session.query(RawJobDB).count()
    assert count == 1
    saved_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/1").first()
    assert saved_job is not None
    assert saved_job.title == "Second"

def test_filter_new_links(test_db_session, repo):
    repo.save_raw_job({"url": "https://example.com/job/1", "title": "Saved"})
    
    unfiltered = [
        {"url": "https://example.com/job/1?ref=test"}, # Canonical is same, should be filtered
        {"url": "https://example.com/job/2"},          # New, should be kept
    ]
    
    new_links = repo.filter_new_links(unfiltered)
    
    assert len(new_links) == 1
    assert new_links[0]["url"] == "https://example.com/job/2"

def test_save_pipeline_run_summary(test_db_session, repo):
    success = repo.save_pipeline_run_summary(
        run_id="test-run-123",
        acquired=10,
        processed=5,
        failed=2
    )
    
    assert success is True
    record = test_db_session.query(PipelineRunDB).filter_by(run_id="test-run-123").first()
    assert record is not None
    assert record.jobs_acquired == 10
    assert record.jobs_processed == 5
    assert record.jobs_failed == 2
    assert record.status == "completed"

def test_save_parsed_job(test_db_session, repo):
    # Setup raw job first (foreign key requirement)
    repo.save_raw_job({"url": "https://example.com/job/parsed", "title": "Raw"})
    raw_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/parsed").first()
    
    parsed = ProcessedJob(
        standardized_title="Clean Title",
        company="Tech Corp",
        job_level="Junior",
        is_internship=False,
        description="Clean desc",
        requirement="None",
        benefit="None",
        cities=["HCM"],
        tech_stack=["Python"],
        technical_competencies=["Coding"],
        domain_knowledge=["Software"]
    )
    
    success = repo.save_parsed_job(
        parsed=parsed,
        raw_job_id=raw_job.id,
        original_url="https://example.com/job/parsed"
    )
    
    assert success is True
    assert raw_job.clean_job is not None
    assert raw_job.clean_job.standardized_title == "Clean Title"
    assert raw_job.clean_job.company == "Tech Corp"
