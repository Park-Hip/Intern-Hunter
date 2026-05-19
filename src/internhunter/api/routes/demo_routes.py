from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select, text

from src.internhunter.common.logging import get_logger
from src.internhunter.embeddings import embedder
from src.internhunter.search.repository import SearchRepository
from src.internhunter.resume import execute_match_resume, execute_upload_resume
from src.internhunter.storage.models import CleanJobDB, RawJobDB

logger = get_logger(__name__)

router = APIRouter()
search_repo = SearchRepository()


class ResumeMatchRequest(BaseModel):
    user_id: str = Field(..., description="User identifier used for storing and matching the resume.")
    resume_text: str = Field(..., description="Plain resume text to embed and match against jobs.")
    limit: int = Field(5, ge=1, description="Maximum number of matches to return.")


def _check_db_connection() -> bool:
    from src.internhunter.storage.session import SessionLocal

    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    return True


def _map_job_row(job: CleanJobDB) -> dict[str, Any]:
    return {
        "title": job.standardized_title or "Unknown",
        "company": job.company or (job.raw_job.company if job.raw_job else None) or "Unknown",
        "cities": list(job.cities) if job.cities else [],
        "url": job.raw_job.url if job.raw_job else "#",
        "salary_range": f"{job.salary_min or '?'} - {job.salary_max or '?'} {job.currency}",
        "match_score": getattr(job, "match_score", None),
    }


def _get_recent_clean_jobs(limit: int) -> list[dict[str, Any]]:
    from src.internhunter.storage.session import SessionLocal

    with SessionLocal() as session:
        statement = (
            select(CleanJobDB)
            .outerjoin(RawJobDB, RawJobDB.id == CleanJobDB.raw_job_id)
            .order_by(desc(CleanJobDB.created_at))
            .limit(limit)
        )
        rows = session.execute(statement).scalars().all()
        return [_map_job_row(job) for job in rows]


@router.get("/health")
def health() -> dict[str, str]:
    try:
        _check_db_connection()
        return {"status": "ok", "db": "ok", "search": "ready"}
    except Exception as exc:
        logger.warning("Health check failed", error=str(exc))
        return {"status": "ok", "db": "error", "search": "degraded"}


@router.get("/jobs/search")
def search_jobs(query: str = "data scientist", limit: int = 5, mode: str = "criteria") -> list[dict[str, Any]]:
    normalized_mode = (mode or "criteria").strip().lower()
    if normalized_mode not in {"criteria", "semantic"}:
        raise HTTPException(status_code=400, detail="mode must be either 'criteria' or 'semantic'.")

    if normalized_mode == "semantic":
        query_text = query.strip() or "data scientist"
        try:
            query_embedding = embedder.generate_embedding(query_text)
        except Exception as exc:
            logger.error("jobs_search semantic embedding failed", error=str(exc))
            raise HTTPException(status_code=500, detail="Failed to generate query embedding.")

        try:
            results = search_repo.search_jobs_by_similarity(query_embedding, limit=limit)
        except Exception as exc:
            logger.error("jobs_search semantic search failed", error=str(exc))
            raise HTTPException(status_code=500, detail="Failed to search jobs semantically.")
        return results

    normalized = query.strip()
    search_terms = [normalized]
    if normalized:
        search_terms.append(normalized.title())

    try:
        for term in search_terms:
            if not term:
                continue
            results = search_repo.search_jobs_by_criteria(title=[term], limit=limit)
            if results:
                return results

        # Criteria search is intentionally strict; fall back to the most recent clean jobs
        # so the MVP demo still returns something useful when standardized titles do not match.
        return _get_recent_clean_jobs(limit)
    except Exception as exc:
        logger.error("jobs_search failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to search jobs.")


@router.post("/resume/match")
def resume_match(request: ResumeMatchRequest) -> list[dict[str, Any]]:
    resume_text = request.resume_text.strip()
    if not resume_text:
        raise HTTPException(status_code=400, detail="resume_text cannot be empty.")

    try:
        upload_result = execute_upload_resume(request.user_id, resume_text)
    except Exception as exc:
        logger.error("resume upload failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to upload resume.")

    if not isinstance(upload_result, str) or not upload_result.startswith("Resume successfully uploaded"):
        logger.error("resume upload returned failure", result=str(upload_result))
        raise HTTPException(status_code=500, detail=str(upload_result))

    try:
        matches = execute_match_resume(request.user_id, limit=request.limit)
    except Exception as exc:
        logger.error("resume match failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to match resume.")

    if not matches:
        raise HTTPException(status_code=404, detail="No matching jobs found.")

    if isinstance(matches, list) and len(matches) == 1 and isinstance(matches[0], dict) and matches[0].get("error"):
        raise HTTPException(status_code=404, detail=matches[0]["error"])

    return matches
