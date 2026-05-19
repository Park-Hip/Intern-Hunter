from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

from pydantic import BaseModel, Field
from sqlalchemy import select

from src.internhunter.common.logging import get_logger
from src.internhunter.embeddings.embedder import Embedder
from src.internhunter.resume.repository import UserProfileRepository
from src.internhunter.search.repository import SearchRepository
from src.internhunter.storage.models import CleanJobDB, RawJobDB
from src.internhunter.storage.session import SessionLocal

logger = get_logger(__name__)

search_repo = SearchRepository()
profile_repo = UserProfileRepository()
embedder = Embedder()

_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "python": ("python",),
    "sql": ("sql",),
    "machine learning": ("machine learning",),
    "deep learning": ("deep learning",),
    "nlp": ("nlp",),
    "computer vision": ("computer vision",),
    "pandas": ("pandas",),
    "numpy": ("numpy",),
    "scikit-learn": ("scikit-learn", "scikit learn"),
    "pytorch": ("pytorch",),
    "tensorflow": ("tensorflow",),
    "fastapi": ("fastapi",),
    "flask": ("flask",),
    "docker": ("docker",),
    "git": ("git",),
    "aws": ("aws",),
    "azure": ("azure",),
    "data visualization": ("data visualization",),
    "statistics": ("statistics",),
    "mlops": ("mlops",),
    "langchain": ("langchain",),
    "embeddings": ("embeddings", "embedding"),
}
_SKILL_ORDER = tuple(_SKILL_ALIASES.keys())
_SKILL_LABELS = {
    "python": "Python",
    "sql": "SQL",
    "machine learning": "machine learning",
    "deep learning": "deep learning",
    "nlp": "NLP",
    "computer vision": "computer vision",
    "pandas": "pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "docker": "Docker",
    "git": "Git",
    "aws": "AWS",
    "azure": "Azure",
    "data visualization": "data visualization",
    "statistics": "statistics",
    "mlops": "MLOps",
    "langchain": "LangChain",
    "embeddings": "embeddings",
}


def is_missing_embedding(embedding: Any) -> bool:
    """Return True when an embedding is absent or empty, without relying on truthiness."""
    if embedding is None:
        return True

    size = getattr(embedding, "size", None)
    if size is not None:
        try:
            return int(size) == 0
        except (TypeError, ValueError):
            pass

    try:
        return len(embedding) == 0
    except TypeError:
        return False


def _normalize_skill_text(text: str) -> str:
    normalized = text.lower()
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def extract_known_skills(text: str) -> set[str]:
    if not text:
        return set()

    normalized_text = _normalize_skill_text(text)
    matched: set[str] = set()

    for canonical_skill, aliases in _SKILL_ALIASES.items():
        for alias in aliases:
            normalized_alias = _normalize_skill_text(alias)
            pattern = r"\b" + re.escape(normalized_alias) + r"\b"
            if re.search(pattern, normalized_text):
                matched.add(canonical_skill)
                break

    return matched


def _format_skill_label(skill: str) -> str:
    return _SKILL_LABELS.get(skill, skill)


def _format_skill_phrase(skills: Iterable[str]) -> str:
    labels = [_format_skill_label(skill) for skill in skills]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def _build_job_text(job: Dict[str, Any]) -> str:
    parts: list[str] = []
    for field_name in ("title", "level", "company"):
        value = job.get(field_name)
        if value:
            parts.append(str(value))

    cities = job.get("cities")
    if cities:
        if isinstance(cities, list):
            parts.append(", ".join(str(city) for city in cities if city))
        else:
            parts.append(str(cities))

    for field_name in ("description", "requirement"):
        value = job.get(field_name)
        if value:
            parts.append(str(value))

    for field_name in ("tech_stack", "technical_competencies", "domain_knowledge"):
        value = job.get(field_name)
        if value:
            if isinstance(value, list):
                parts.append(", ".join(str(item) for item in value if item))
            else:
                parts.append(str(value))

    return "\n".join(part for part in parts if part)


def build_job_explanation(resume_text: str, job: Dict[str, Any]) -> Dict[str, Any]:
    resume_skills = extract_known_skills(resume_text or "")
    job_text = _build_job_text(job)
    job_skills = extract_known_skills(job_text)

    matched_skills = [skill for skill in _SKILL_ORDER if skill in resume_skills and skill in job_skills]
    unmatched_resume_skills = [skill for skill in _SKILL_ORDER if skill in resume_skills and skill not in job_skills]

    if not resume_skills:
        reason = "Resume text did not contain recognized skills from the current keyword list."
    elif matched_skills:
        reason = f"Strong overlap on {_format_skill_phrase(matched_skills[:3])}." if len(matched_skills) >= 3 else f"Some overlap on {_format_skill_phrase(matched_skills[:2])}."
    else:
        if job.get("match_score") is not None:
            reason = "Matched primarily by semantic similarity; no explicit skill overlap found."
        else:
            reason = "No explicit skill overlap found."

    return {
        "matched_skills": matched_skills,
        "unmatched_resume_skills": unmatched_resume_skills,
        "reason": reason,
    }


def _fetch_job_context_by_url(url: str) -> Dict[str, Any]:
    if not url:
        return {}

    with SessionLocal() as session:
        statement = (
            select(CleanJobDB, RawJobDB)
            .join(RawJobDB, RawJobDB.id == CleanJobDB.raw_job_id)
            .where(RawJobDB.url == url)
            .limit(1)
        )
        row = session.execute(statement).first()
        if not row:
            return {}

        clean_job, raw_job = row
        return {
            "title": clean_job.standardized_title or raw_job.title or "",
            "level": clean_job.job_level or "",
            "company": clean_job.company or raw_job.company or "",
            "cities": list(clean_job.cities) if clean_job.cities else [],
            "description": clean_job.description,
            "requirement": clean_job.requirement,
            "tech_stack": list(clean_job.tech_stack) if clean_job.tech_stack else [],
            "technical_competencies": list(clean_job.technical_competencies) if clean_job.technical_competencies else [],
            "domain_knowledge": list(clean_job.domain_knowledge) if clean_job.domain_knowledge else [],
        }


def _augment_match_result(resume_text: str, job: Dict[str, Any]) -> Dict[str, Any]:
    augmented = dict(job)
    job_context = _fetch_job_context_by_url(job.get("url") or "")
    if job_context:
        for key, value in job_context.items():
            augmented.setdefault(key, value)

    explanation = build_job_explanation(resume_text, augmented)
    augmented.update(explanation)
    return augmented


class MatchResumeArgs(BaseModel):
    user_id: str = Field(..., description="The unique ID of the user whose resume should be used for matching.")
    limit: int = Field(5, description="The maximum number of matches to return.")


class UploadResumeArgs(BaseModel):
    user_id: str = Field(..., description="The unique ID to associate with this resume.")
    resume_text: str = Field(..., description="The full text content of the resume.")


def execute_match_resume(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        profile = profile_repo.get_user_profile(user_id)
        if profile is None:
            return [{"error": "No resume found for this user. Please upload a resume first."}]

        resume_embedding = profile.get("resume_embedding")
        if is_missing_embedding(resume_embedding):
            return [{"error": "No resume found for this user. Please upload a resume first."}]

        results = search_repo.search_jobs_by_similarity(resume_embedding, limit=limit)
        if not isinstance(results, list):
            return results

        if len(results) == 1 and isinstance(results[0], dict) and results[0].get("error"):
            return results

        return [_augment_match_result(profile.get("resume_text") or "", job) if isinstance(job, dict) else job for job in results]
    except Exception as e:
        logger.error("execute_match_resume failed", error=str(e))
        return [{"error": f"Failed to match resume: {str(e)}"}]


def execute_upload_resume(user_id: str, resume_text: str) -> str:
    try:
        embedding = embedder.generate_embedding(resume_text)
        if profile_repo.save_user_profile(user_id, resume_text, embedding):
            return "Resume successfully uploaded and vectorized. You can now ask me to match jobs based on your profile!"
        return "Failed to save resume to the database."
    except Exception as e:
        logger.error("execute_upload_resume failed", error=str(e))
        return f"Error uploading resume: {str(e)}"


__all__ = [
    "MatchResumeArgs",
    "UploadResumeArgs",
    "execute_match_resume",
    "execute_upload_resume",
    "build_job_explanation",
    "extract_known_skills",
    "is_missing_embedding",
    "profile_repo",
    "search_repo",
    "embedder",
]
