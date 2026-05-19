import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func, text

from src.internhunter.storage.session import engine, SessionLocal
from src.internhunter.storage.models import Base, RawJobDB, CleanJobDB, AuditJobDB, PipelineRunDB
from src.core.models import ProcessedJob, RawJob
from src.core.utils import normalize_url
from src.internhunter.common.logging import get_logger

logger = get_logger(__name__)


_BLOCKED_AUDIT_PHRASES = (
    "blocked_or_empty_content",
    "sorry, you have been blocked",
    "please enable cookies",
    "you are unable to access topcv.vn",
    "cloudflare ray id",
    "performance & security by",
)


class ETLRepository:
    def create_tables(self):
        """Create raw_jobs and clean_jobs tables."""
        Base.metadata.create_all(bind=engine)
        self._sync_sequences()
        logger.info("Database tables verified/created")

    def _sync_sequences(self):
        """Reset PostgreSQL auto-increment sequences to match current max IDs."""
        tables = ["raw_jobs", "clean_jobs"]
        with SessionLocal() as session:
            for table in tables:
                try:
                    seq_query = text("SELECT pg_get_serial_sequence(:table, 'id')")
                    seq_name = session.execute(seq_query, {"table": table}).scalar()
                    if not seq_name:
                        continue
                    reset_query = text(
                        f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)"
                    )
                    new_val = session.execute(reset_query).scalar()
                    session.commit()
                    logger.info("Sequence synced", table=table, sequence=seq_name, next_val=new_val)
                except Exception as e:
                    session.rollback()
                    logger.warning("Failed to sync sequence", table=table, error=str(e))

    def get_raw_jobs_count(self) -> int:
        """Returns the total count of raw jobs in the database."""
        with SessionLocal() as session:
            try:
                statement = select(func.count()).select_from(RawJobDB)
                result = session.execute(statement).scalar()
                return result if result else 0
            except Exception as e:
                logger.error(f"Error counting raw jobs: {e}")
                return 0

    def get_raw_job_by_id(self, raw_job_id) -> RawJob:
        with SessionLocal() as session:
            try:
                statement = select(RawJobDB).where(RawJobDB.id == raw_job_id)
                result = session.execute(statement).scalar()
                return result
            except Exception as e:
                logger.error("Failed to get raw job by id", error=str(e))

    def filter_new_links(self, unfiltered_links: List[dict]) -> List[dict]:
        """Filters out links that already exist in the raw_jobs."""
        if not unfiltered_links:
            return []

        normalized_links_map = {}
        for link in unfiltered_links:
            url = link.get("url", "")
            norm = normalize_url(url)
            if norm:
                normalized_links_map[norm] = link

        if not normalized_links_map:
            return []

        potential_urls = list(normalized_links_map.keys())
        new_links = []
        with SessionLocal() as session:
            try:
                statement = select(RawJobDB.url).where(RawJobDB.url.in_(potential_urls))
                existing_urls_result = session.execute(statement).scalars().all()
                existing_urls = set(existing_urls_result)

                for url, link in normalized_links_map.items():
                    if url not in existing_urls:
                        link["url"] = url
                        new_links.append(link)
            except Exception as e:
                logger.error(f"Error filtering new links: {e}")
                return []
        return new_links

    def save_raw_job(self, job_data: Dict[str, Any]) -> bool:
        """Saves a single raw job to the database.

        If the URL already exists, refresh the existing snapshot instead of failing.
        """
        with SessionLocal() as session:
            try:
                now = datetime.now(timezone.utc)
                existing = session.execute(
                    select(RawJobDB).where(RawJobDB.url == job_data["url"])
                ).scalar_one_or_none()

                if existing:
                    crawl_run_id = job_data.get("crawl_run_id", existing.crawl_run_id)
                    source_seed_url = job_data.get("source_seed_url", existing.source_seed_url)
                    existing.title = job_data.get("title")
                    existing.company = job_data.get("company")
                    existing.location = job_data.get("location")
                    existing.full_json_dump = job_data.get("full_json_dump")
                    existing.status = job_data.get("status", existing.status or "pending")
                    existing.extraction_method = job_data.get("extraction_method", existing.extraction_method or "css")
                    existing.raw_markdown = job_data.get("raw_markdown")
                    if "html_content" in job_data:
                        existing.html_content = job_data.get("html_content")
                    if "screenshot_path" in job_data:
                        existing.screenshot_path = job_data.get("screenshot_path")
                    existing.crawl_run_id = crawl_run_id
                    existing.source_seed_url = source_seed_url
                    existing.updated_at = now
                    existing.last_crawled_at = now
                    existing.retry_count = (existing.retry_count or 0) + 1
                    session.commit()
                    logger.info(
                        "Existing raw job refreshed",
                        url=job_data.get("url"),
                        raw_job_id=existing.id,
                        crawl_run_id=crawl_run_id,
                        source_seed_url=source_seed_url,
                        updated_at=existing.updated_at,
                        last_crawled_at=existing.last_crawled_at,
                        screenshot_path=existing.screenshot_path,
                        retry_count=existing.retry_count,
                    )
                    return True

                raw_job = RawJobDB(
                    url=job_data["url"],
                    crawl_run_id=job_data.get("crawl_run_id"),
                    source_seed_url=job_data.get("source_seed_url"),
                    title=job_data.get("title"),
                    company=job_data.get("company"),
                    location=job_data.get("location"),
                    full_json_dump=job_data.get("full_json_dump"),
                    status=job_data.get("status", "pending"),
                    extraction_method=job_data.get("extraction_method", "css"),
                    raw_markdown=job_data.get("raw_markdown"),
                    html_content=job_data.get("html_content"),
                    screenshot_path=job_data.get("screenshot_path"),
                    retry_count=job_data.get("retry_count", 0),
                    updated_at=now,
                    last_crawled_at=now,
                )
                session.add(raw_job)
                session.commit()
                return True
            except IntegrityError:
                session.rollback()
                logger.warning(f"Duplicate job found (URL collision): {job_data.get('url')}")
                return False
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to save raw job {job_data.get('url')}: {e}")
                return False

    def save_to_audit(self, audit_data: Dict[str, Any]) -> bool:
        """Saves a failed job entry to the audit_jobs (DLQ)."""
        with SessionLocal() as session:
            try:
                audit_entry = AuditJobDB(
                    url=audit_data["url"],
                    crawl_run_id=audit_data.get("crawl_run_id"),
                    source_seed_url=audit_data.get("source_seed_url"),
                    error_type=audit_data.get("error_type"),
                    error_message=audit_data.get("error_message"),
                    screenshot_path=audit_data.get("screenshot_path"),
                    html_content=audit_data.get("html_content"),
                )
                session.add(audit_entry)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to save to audit: {e}")
                return False

    @staticmethod
    def _is_blocked_audit_message(error_type: str | None, error_message: str | None) -> bool:
        if not error_message:
            return error_type == "BOT_DETECTED"
        normalized = error_message.strip().lower()
        if error_type == "BOT_DETECTED":
            return True
        return any(phrase in normalized for phrase in _BLOCKED_AUDIT_PHRASES)

    def get_recently_blocked_urls(self, urls: list[str], cooldown_minutes: int = 60) -> set[str]:
        """Return URLs that have a recent blocked audit within the cooldown window."""
        if not urls:
            return set()

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(cooldown_minutes, 0))
        with SessionLocal() as session:
            try:
                rows = (
                    session.query(AuditJobDB.url, AuditJobDB.error_type, AuditJobDB.error_message)
                    .filter(AuditJobDB.url.in_(urls))
                    .filter(AuditJobDB.created_at >= cutoff)
                    .all()
                )
                blocked_urls = set()
                for url, error_type, error_message in rows:
                    if self._is_blocked_audit_message(error_type, error_message):
                        blocked_urls.add(url)
                return blocked_urls
            except Exception as e:
                logger.error("Failed to query recently blocked urls", error=str(e))
                return set()

    @staticmethod
    def _row_to_raw_job(row) -> RawJob:
        """Convert a RawJobDB ORM row to a RawJob Pydantic model."""
        return RawJob(
            id=row.id,
            url=row.url,
            crawl_run_id=row.crawl_run_id,
            source_seed_url=row.source_seed_url,
            title=row.title,
            company=row.company,
            location=row.location,
            full_json_dump=json.dumps(row.full_json_dump) if row.full_json_dump else "{}",
            status=row.status,
            extraction_method=row.extraction_method,
            raw_markdown=row.raw_markdown,
            html_content=row.html_content,
            screenshot_path=row.screenshot_path,
            retry_count=row.retry_count,
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
            last_crawled_at=row.last_crawled_at.isoformat() if row.last_crawled_at else None,
        )

    def fetch_pending_raw_jobs(self, limit: int = 100, crawl_run_id: str | None = None) -> List[RawJob]:
        """Fetches jobs that are 'pending' and need processing."""
        with SessionLocal() as session:
            try:
                statement = select(RawJobDB).where(RawJobDB.status == "pending")
                if crawl_run_id is not None:
                    statement = statement.where(RawJobDB.crawl_run_id == crawl_run_id)
                statement = statement.order_by(RawJobDB.retry_count.desc(), RawJobDB.id.desc()).limit(limit)
                results = session.execute(statement).scalars().all()
                return [self._row_to_raw_job(row) for row in results]
            except Exception as e:
                logger.error(f"Error fetching pending raw jobs: {e}")
                return []

    def update_job_status(self, job_id: int, status: str, retry_increment: bool = False) -> bool:
        """Updates the status of a raw job."""
        with SessionLocal() as session:
            try:
                job = session.get(RawJobDB, job_id)
                if job:
                    job.status = status
                    if retry_increment:
                        job.retry_count += 1
                    session.commit()
                    return True
                return False
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update job status: {e}")
                return False

    def fetch_unparsed_jobs(self, limit: int = 100) -> List[RawJob]:
        """Fetches jobs that have not been parsed yet (not in clean_jobs)."""
        with SessionLocal() as session:
            try:
                statement = (
                    select(RawJobDB)
                    .outerjoin(CleanJobDB, RawJobDB.id == CleanJobDB.raw_job_id)
                    .where(CleanJobDB.id.is_(None))
                    .limit(limit)
                )
                results = session.execute(statement).scalars().all()
                return [self._row_to_raw_job(row) for row in results]
            except Exception as e:
                logger.error(f"Error fetching unparsed jobs: {e}")
                return []

    def save_parsed_job(self, parsed: ProcessedJob, raw_job_id: int, original_url: str, embedding: list = None) -> bool:
        """Saves parsed job data with proper relationships and optional embedding."""
        with SessionLocal() as session:
            try:
                existing = session.execute(
                    select(CleanJobDB).where(CleanJobDB.raw_job_id == raw_job_id)
                ).scalar_one_or_none()
                if existing:
                    logger.warning("Clean job already exists, skipping", raw_job_id=raw_job_id, url=original_url)
                    return True

                clean_job = CleanJobDB(
                    raw_job_id=raw_job_id,
                    standardized_title=parsed.standardized_title,
                    company=parsed.company,
                    job_level=parsed.job_level,
                    is_internship=parsed.is_internship,
                    description=parsed.description,
                    requirement=parsed.requirement,
                    benefit=parsed.benefit,
                    cities=parsed.cities,
                    experience=parsed.experience,
                    min_gpa=parsed.min_gpa,
                    english_requirement=parsed.english_requirement,
                    salary_min=parsed.salary_min,
                    salary_max=parsed.salary_max,
                    currency=parsed.currency,
                    is_salary_negotiable=parsed.is_salary_negotiable,
                    tech_stack=parsed.tech_stack,
                    technical_competencies=parsed.technical_competencies,
                    domain_knowledge=parsed.domain_knowledge,
                    embedding=embedding,
                )
                session.add(clean_job)
                session.commit()
                return True
            except IntegrityError as e:
                session.rollback()
                logger.error("Integrity error saving parsed job", original_url=original_url, error=str(e))
                return False
            except Exception as e:
                session.rollback()
                logger.error("Failed to save parsed job", original_url=original_url, error=str(e))
                return False

    def save_pipeline_run_summary(self, run_id: str, acquired: int, processed: int, failed: int, status: str = "completed") -> bool:
        """Saves a summary record for the ETL pipeline execution."""
        with SessionLocal() as session:
            try:
                run_record = PipelineRunDB(
                    run_id=run_id,
                    jobs_acquired=acquired,
                    jobs_processed=processed,
                    jobs_failed=failed,
                    status=status,
                )
                session.add(run_record)
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to save pipeline run summary: {e}")
                return False


# Module-level singleton (like llm_router)
etl_repo = ETLRepository()


__all__ = ["ETLRepository", "etl_repo"]
