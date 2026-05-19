from __future__ import annotations

from typing import Any, Dict, List

import sqlalchemy as db
from sqlalchemy import select

from src.internhunter.common.logging import get_logger
from src.internhunter.storage.models import CleanJobDB, RawJobDB
from src.internhunter.storage.session import SessionLocal

logger = get_logger(__name__)


def _distance_to_match_score(distance: Any) -> float:
    """Convert pgvector cosine distance into a bounded similarity-style score."""
    if distance is None:
        return 0.0

    try:
        score = 1.0 - float(distance)
    except (TypeError, ValueError):
        return 0.0

    return round(max(0.0, min(1.0, score)), 6)


def _safe_len(value: Any) -> int | None:
    try:
        return len(value)
    except TypeError:
        return None


class SearchRepository:
    def search_jobs_by_criteria(
        self,
        title: List[str] = None,
        job_level: List[str] = None,
        cities: List[str] = None,
        experience: int = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Dynamically applies filters based on what the user asked for.
        """
        try:
            with SessionLocal() as session:
                statement = select(CleanJobDB).outerjoin(RawJobDB, RawJobDB.id == CleanJobDB.raw_job_id)

                if title:
                    statement = statement.where(CleanJobDB.standardized_title.in_(title))
                if job_level:
                    statement = statement.where(CleanJobDB.job_level.in_(job_level))
                if experience is not None:
                    statement = statement.where(CleanJobDB.experience <= experience)
                if cities:
                    from sqlalchemy import or_

                    city_conditions = [CleanJobDB.cities.cast(db.String).ilike(f"%{city}%") for city in cities]
                    statement = statement.where(or_(*city_conditions))

                statement = statement.limit(limit)
                result = session.execute(statement).scalars().all()

                mapped_jobs = []
                for job in result:
                    mapped_jobs.append(
                        {
                            "title": job.standardized_title or "Unknown",
                            "level": job.job_level or "Unknown",
                            "company": job.company or (job.raw_job.company if job.raw_job else None) or "Unknown",
                            "cities": list(job.cities) if job.cities else [],
                            "experience_required_years": job.experience,
                            "salary_range": f"{job.salary_min or '?'} - {job.salary_max or '?'} {job.currency}",
                            "tech_stack": list(job.tech_stack) if job.tech_stack else [],
                            "url": job.raw_job.url if job.raw_job else "#",
                        }
                    )
                return mapped_jobs
        except Exception as e:
            logger.error(f"Failed to search job by criteria: {e}")
            return []

    def search_jobs_by_similarity(
        self,
        embedding: List[float],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Uses pgvector for Cosine Similarity search.
        """
        try:
            with SessionLocal() as session:
                logger.info(
                    "search_jobs_by_similarity start",
                    query_embedding_type=type(embedding).__name__,
                    query_embedding_length=_safe_len(embedding),
                )

                distance_fn = getattr(CleanJobDB.embedding, "cosine_distance", None)
                if callable(distance_fn):
                    distance_expr = distance_fn(embedding).label("distance")
                else:
                    distance_expr = CleanJobDB.embedding.op("<=>")(embedding).label("distance")

                logger.debug(
                    "search_jobs_by_similarity distance expression",
                    distance_expr_type=type(distance_expr).__name__,
                    distance_expr=str(distance_expr),
                )

                statement = (
                    select(
                        CleanJobDB.id.label("clean_job_id"),
                        CleanJobDB.standardized_title.label("title"),
                        CleanJobDB.job_level.label("level"),
                        CleanJobDB.cities.label("cities"),
                        CleanJobDB.experience.label("experience_required_years"),
                        CleanJobDB.salary_min.label("salary_min"),
                        CleanJobDB.salary_max.label("salary_max"),
                        CleanJobDB.currency.label("currency"),
                        CleanJobDB.company.label("company"),
                        RawJobDB.url.label("url"),
                        distance_expr,
                    )
                    .select_from(CleanJobDB)
                    .outerjoin(RawJobDB, RawJobDB.id == CleanJobDB.raw_job_id)
                    .order_by(distance_expr)
                    .limit(limit)
                )
                result = session.execute(statement).mappings().all()
                logger.debug(
                    "search_jobs_by_similarity result batch",
                    result_type=type(result).__name__,
                    result_count=len(result),
                )

                mapped_jobs = []
                for row in result:
                    logger.debug(
                        "search_jobs_by_similarity row",
                        row_type=type(row).__name__,
                        row_keys=list(row.keys()) if hasattr(row, "keys") else None,
                        distance_type=type(row.get("distance")).__name__ if hasattr(row, "get") else None,
                        distance_value=row.get("distance") if hasattr(row, "get") else None,
                    )
                    distance = row.get("distance")
                    if distance is None:
                        logger.warning("Skipping similarity row with missing distance", row_type=type(row).__name__)
                        continue
                    mapped_jobs.append(
                        {
                            "title": row.get("title") or "Unknown",
                            "level": row.get("level") or "Unknown",
                            "company": row.get("company") or "Unknown",
                            "cities": list(row.get("cities") or []),
                            "experience_required_years": row.get("experience_required_years"),
                            "salary_range": f"{row.get('salary_min') or '?'} - {row.get('salary_max') or '?'} {row.get('currency')}",
                            "url": row.get("url") or "#",
                            "match_score": _distance_to_match_score(distance),
                        }
                    )
                if result and not mapped_jobs:
                    logger.warning(
                        "search_jobs_by_similarity returned rows but no mapped jobs",
                        result_count=len(result),
                    )
                return mapped_jobs
        except Exception as e:
            logger.error(f"Failed to search jobs by similarity: {e}")
            return []

__all__ = [
    "SearchRepository",
    "_distance_to_match_score",
]
