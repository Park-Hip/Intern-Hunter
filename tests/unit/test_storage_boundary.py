from datetime import datetime, timedelta, timezone

from src.internhunter.storage.models import (
    Base as NewBase,
    RawJobDB as NewRawJobDB,
    AuditJobDB as NewAuditJobDB,
    CleanJobDB as NewCleanJobDB,
    PipelineRunDB as NewPipelineRunDB,
)
from src.internhunter.storage.repositories.etl import ETLRepository as NewETLRepository
from src.internhunter.search.repository import SearchRepository as NewSearchRepository
from src.internhunter.resume.repository import UserProfileRepository as NewUserProfileRepository
from src.internhunter.storage.session import SessionLocal as NewSessionLocal, engine as NewEngine
from src.internhunter.storage.models import RawJobDB, AuditJobDB


def test_storage_model_and_session_imports():
    assert NewBase is not None
    assert NewRawJobDB is not None
    assert NewAuditJobDB is not None
    assert NewCleanJobDB is not None
    assert NewPipelineRunDB is not None
    assert NewEngine is not None
    assert NewSessionLocal is not None


def test_storage_repository_imports():
    assert NewETLRepository is not None
    assert NewSearchRepository is not None
    assert NewUserProfileRepository is not None


def test_canonical_etl_repository_writes_raw_job(test_db_session):
    repo = NewETLRepository()
    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/storage-boundary",
            "crawl_run_id": "run-storage-boundary",
            "source_seed_url": "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
            "title": "Storage Boundary Job",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"foo": "bar"},
            "status": "pending",
            "raw_markdown": "markdown body",
            "html_content": "<html><body>storage boundary</body></html>",
            "screenshot_path": "C:/tmp/storage-boundary.png",
        }
    )

    saved_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/storage-boundary").first()
    assert saved_job is not None
    assert saved_job.title == "Storage Boundary Job"
    assert saved_job.status == "pending"
    assert saved_job.crawl_run_id == "run-storage-boundary"
    assert saved_job.source_seed_url == "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"
    assert saved_job.created_at is not None
    assert saved_job.updated_at is not None
    assert saved_job.last_crawled_at is not None
    assert saved_job.raw_markdown == "markdown body"
    assert saved_job.html_content == "<html><body>storage boundary</body></html>"
    assert saved_job.screenshot_path == "C:/tmp/storage-boundary.png"


def test_canonical_etl_repository_refreshes_duplicate_raw_job(test_db_session):
    repo = NewETLRepository()
    first_payload = {
        "url": "https://example.com/job/storage-duplicate",
        "crawl_run_id": "run-storage-old",
        "source_seed_url": "https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
        "title": "Initial Title",
        "company": "Boundary Co",
        "location": "Remote",
        "full_json_dump": {"version": 1},
        "status": "pending",
        "retry_count": 0,
    }
    refreshed_payload = {
        "url": "https://example.com/job/storage-duplicate",
        "crawl_run_id": "run-storage-new",
        "source_seed_url": "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
        "title": "Refreshed Title",
        "company": "Boundary Co 2",
        "location": "Hanoi",
        "full_json_dump": {"version": 2},
        "status": "pending",
        "extraction_method": "raw",
        "raw_markdown": "updated markdown",
        "html_content": "<html><body>updated</body></html>",
        "screenshot_path": "C:/tmp/topcv-shot.png",
    }

    assert repo.save_raw_job(first_payload)
    initial_row = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/storage-duplicate").first()
    assert initial_row is not None
    initial_created_at = initial_row.created_at

    assert repo.save_raw_job(refreshed_payload)
    test_db_session.expire_all()

    saved_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/storage-duplicate").first()
    assert saved_job is not None
    assert saved_job.title == "Refreshed Title"
    assert saved_job.company == "Boundary Co 2"
    assert saved_job.location == "Hanoi"
    assert saved_job.full_json_dump == {"version": 2}
    assert saved_job.extraction_method == "raw"
    assert saved_job.raw_markdown == "updated markdown"
    assert saved_job.html_content == "<html><body>updated</body></html>"
    assert saved_job.screenshot_path == "C:/tmp/topcv-shot.png"
    assert saved_job.crawl_run_id == "run-storage-new"
    assert saved_job.source_seed_url == "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"
    assert saved_job.retry_count == 1
    assert saved_job.created_at == initial_created_at
    assert saved_job.updated_at is not None
    assert saved_job.last_crawled_at is not None


def test_canonical_etl_repository_persists_html_and_screenshot_on_refresh(test_db_session):
    repo = NewETLRepository()
    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/html-refresh",
            "crawl_run_id": "run-html-old",
            "title": "Initial",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"version": 1},
            "status": "pending",
            "extraction_method": "css",
            "raw_markdown": "initial",
            "html_content": "<html><body>initial</body></html>",
            "screenshot_path": "C:/tmp/initial.png",
        }
    )
    initial_row = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/html-refresh").first()
    assert initial_row is not None
    initial_created_at = initial_row.created_at

    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/html-refresh",
            "crawl_run_id": "run-html-new",
            "title": "Updated",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"version": 2},
            "status": "pending",
            "extraction_method": "css",
            "raw_markdown": "updated",
            "html_content": "<html><body>updated</body></html>",
            "screenshot_path": "C:/tmp/updated.png",
        }
    )

    test_db_session.expire_all()
    saved_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/html-refresh").first()
    assert saved_job is not None
    assert saved_job.created_at == initial_created_at
    assert saved_job.crawl_run_id == "run-html-new"
    assert saved_job.html_content == "<html><body>updated</body></html>"
    assert saved_job.screenshot_path == "C:/tmp/updated.png"


def test_canonical_etl_repository_filters_existing_links(test_db_session):
    repo = NewETLRepository()
    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/dedup-existing",
            "title": "Existing Job",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"foo": "bar"},
            "status": "pending",
        }
    )

    filtered = repo.filter_new_links(
        [
            {"url": "https://example.com/job/dedup-existing"},
            {"url": "https://example.com/job/dedup-new"},
        ]
    )

    assert len(filtered) == 1
    assert filtered[0]["url"] == "https://example.com/job/dedup-new"


def test_canonical_etl_repository_prioritizes_refreshed_pending_jobs(test_db_session):
    repo = NewETLRepository()
    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/older-pending",
            "crawl_run_id": "run-old",
            "title": "Older Pending",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"foo": "bar"},
            "status": "pending",
        }
    )
    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/current-run",
            "crawl_run_id": "run-current",
            "title": "Current Run",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"foo": "bar"},
            "status": "pending",
        }
    )
    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/current-run",
            "crawl_run_id": "run-current",
            "title": "Current Run Refreshed",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"foo": "bar"},
            "status": "pending",
            "extraction_method": "raw",
            "raw_markdown": "refreshed",
        }
    )

    pending_jobs = repo.fetch_pending_raw_jobs(limit=1)

    assert len(pending_jobs) == 1
    assert pending_jobs[0].url == "https://example.com/job/current-run"
    assert pending_jobs[0].crawl_run_id == "run-current"
    assert pending_jobs[0].retry_count == 1


def test_canonical_etl_repository_fetches_pending_jobs_for_crawl_run_id_only(test_db_session):
    repo = NewETLRepository()
    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/run-a-1",
            "crawl_run_id": "run-a",
            "title": "Run A 1",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"foo": "bar"},
            "status": "pending",
        }
    )
    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/run-b-1",
            "crawl_run_id": "run-b",
            "title": "Run B 1",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"foo": "bar"},
            "status": "pending",
        }
    )
    assert repo.save_raw_job(
        {
            "url": "https://example.com/job/run-b-2",
            "crawl_run_id": "run-b",
            "title": "Run B 2",
            "company": "Boundary Co",
            "location": "Remote",
            "full_json_dump": {"foo": "bar"},
            "status": "pending",
        }
    )

    scoped_jobs = repo.fetch_pending_raw_jobs(limit=10, crawl_run_id="run-b")

    assert len(scoped_jobs) == 2
    assert {job.crawl_run_id for job in scoped_jobs} == {"run-b"}
    assert all(job.status == "pending" for job in scoped_jobs)


def test_canonical_etl_repository_detects_recently_blocked_urls_with_cooldown(test_db_session):
    repo = NewETLRepository()
    recent_blocked_url = "https://example.com/job/recent-blocked"
    old_blocked_url = "https://example.com/job/old-blocked"
    recent_non_blocked_url = "https://example.com/job/recent-nonblocked"

    test_db_session.add_all(
        [
            NewAuditJobDB(
                url=recent_blocked_url,
                error_type="BOT_DETECTED",
                error_message="blocked_or_empty_content",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            ),
            NewAuditJobDB(
                url=old_blocked_url,
                error_type="BOT_DETECTED",
                error_message="blocked_or_empty_content",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=120),
            ),
            NewAuditJobDB(
                url=recent_non_blocked_url,
                error_type="CRAWL_FAILED",
                error_message="crawl_timeout",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            ),
        ]
    )
    test_db_session.commit()

    blocked_urls = repo.get_recently_blocked_urls(
        [recent_blocked_url, old_blocked_url, recent_non_blocked_url],
        cooldown_minutes=60,
    )

    assert blocked_urls == {recent_blocked_url}


def test_canonical_etl_repository_writes_audit_rows_with_run_and_source_metadata(test_db_session):
    repo = NewETLRepository()
    assert repo.save_to_audit(
        {
            "url": "https://example.com/job/audit-metadata",
            "crawl_run_id": "run-audit-metadata",
            "source_seed_url": "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
            "error_type": "CRAWL_FAILED",
            "error_message": "crawl_timeout",
        }
    )

    saved_audit = test_db_session.query(AuditJobDB).filter_by(url="https://example.com/job/audit-metadata").first()
    assert saved_audit is not None
    assert saved_audit.crawl_run_id == "run-audit-metadata"
    assert saved_audit.source_seed_url == "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"


def test_canonical_etl_repository_allows_legacy_audit_rows_without_run_metadata(test_db_session):
    repo = NewETLRepository()
    assert repo.save_to_audit(
        {
            "url": "https://example.com/job/legacy-audit",
            "error_type": "CRAWL_FAILED",
            "error_message": "crawl_timeout",
        }
    )

    saved_audit = test_db_session.query(AuditJobDB).filter_by(url="https://example.com/job/legacy-audit").first()
    assert saved_audit is not None
    assert saved_audit.crawl_run_id is None
    assert saved_audit.source_seed_url is None


def test_canonical_etl_repository_refreshes_blocked_raw_job_updates_crawl_timestamp(test_db_session):
    repo = NewETLRepository()
    url = "https://example.com/job/blocked-refresh"
    assert repo.save_raw_job(
        {
            "url": url,
            "crawl_run_id": "run-blocked-old",
            "source_seed_url": "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
            "title": "Unknown (RAW)",
            "company": "Unknown (RAW)",
            "location": "Unknown",
            "full_json_dump": {"is_blocked": True},
            "status": "blocked",
            "extraction_method": "raw",
            "raw_markdown": "blocked markdown",
        }
    )

    initial_row = test_db_session.query(RawJobDB).filter_by(url=url).first()
    assert initial_row is not None
    initial_created_at = initial_row.created_at

    assert repo.save_raw_job(
        {
            "url": url,
            "crawl_run_id": "run-blocked-new",
            "source_seed_url": "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
            "title": "Unknown (RAW)",
            "company": "Unknown (RAW)",
            "location": "Unknown",
            "full_json_dump": {"is_blocked": True},
            "status": "blocked",
            "extraction_method": "raw",
            "raw_markdown": "blocked markdown refreshed",
        }
    )

    test_db_session.expire_all()
    refreshed_row = test_db_session.query(RawJobDB).filter_by(url=url).first()
    assert refreshed_row is not None
    assert refreshed_row.created_at == initial_created_at
    assert refreshed_row.crawl_run_id == "run-blocked-new"
    assert refreshed_row.last_crawled_at is not None
    assert refreshed_row.updated_at is not None

