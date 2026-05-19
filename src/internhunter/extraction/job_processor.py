import asyncio
import json
import time

from src.internhunter.llm.router import llm_router
from src.internhunter.storage.repositories.etl import ETLRepository
from src.internhunter.embeddings.embedder import Embedder
from src.core.models import ProcessedJob, RawJob
from src.internhunter.llm.base import LLMProvider
from src.internhunter.config.settings import settings
from src.internhunter.common.logging import get_logger

logger = get_logger(__name__)

# Processor contract:
# - direct raw mapping: description, requirements, benefits
# - deterministic parser hints: location normalization, internship detection
# - LLM context building: preferred structured TopCV context + legacy fallback
# - deterministic evaluation: no LLM calls, no embeddings

_TOPCV_SECTION_ORDER = ("description", "requirements", "benefits")
_TOPCV_SECTION_HEADING = {
    "description": "Mô tả công việc",
    "requirements": "Yêu cầu ứng viên",
    "benefits": "Quyền lợi",
}

_INTERNSHIP_HINTS = (
    "intern",
    "internship",
    "fresher",
    "thực tập",
    "thuc tap",
    "trainee",
)

_VALIDATION_PRIORITY_KEYS = (
    "title",
    "company",
    "location",
    "salary",
    "experience",
    "info",
    "description",
    "requirement",
    "benefit",
)
_VALIDATION_NOISY_KEYS = {
    "error",
    "is_blocked",
    "blocked_reason",
    "retry_count",
    "status",
    "extraction_method",
    "created_at",
    "updated_at",
}


def _iter_useful_text(value, *, key: str | None = None, depth: int = 0, max_depth: int = 4):
    """Yield readable text fragments from nested job payloads."""
    if value is None or depth > max_depth:
        return

    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                parsed = json.loads(text)
            except Exception:
                yield text
            else:
                if isinstance(parsed, (dict, list)):
                    yield from _iter_useful_text(parsed, key=key, depth=depth + 1, max_depth=max_depth)
                else:
                    parsed_text = str(parsed).strip()
                    if parsed_text:
                        yield parsed_text
        return

    if isinstance(value, (int, float, bool)):
        return

    if isinstance(value, list):
        for item in value:
            yield from _iter_useful_text(item, key=key, depth=depth + 1, max_depth=max_depth)
        return

    if isinstance(value, dict):
        keys = list(value.keys())
        ordered_keys = [k for k in _VALIDATION_PRIORITY_KEYS if k in value]
        ordered_keys.extend(
            k for k in keys
            if k not in ordered_keys and k not in _VALIDATION_NOISY_KEYS
        )

        for child_key in ordered_keys:
            yield from _iter_useful_text(
                value.get(child_key),
                key=child_key,
                depth=depth + 1,
                max_depth=max_depth,
            )


def build_validation_text(job) -> str:
    """Build readable validation text from raw job fields and extracted payloads."""
    parts = []

    for field_name in ("title", "company", "location"):
        value = getattr(job, field_name, None)
        if value:
            text = str(value).strip()
            if text:
                parts.append(text)

    raw_markdown = getattr(job, "raw_markdown", None)
    if raw_markdown:
        raw_text = str(raw_markdown).strip()
        if raw_text:
            parts.append(raw_text)

    full_json_dump = getattr(job, "full_json_dump", None)
    if full_json_dump:
        for fragment in _iter_useful_text(full_json_dump):
            if fragment and fragment not in parts:
                parts.append(fragment)

    return "\n".join(parts)


def _safe_load_raw_json_dump(full_json_dump) -> dict:
    if not full_json_dump:
        return {}

    if isinstance(full_json_dump, dict):
        return full_json_dump

    if not isinstance(full_json_dump, str):
        return {}

    try:
        parsed = json.loads(full_json_dump)
    except (TypeError, json.JSONDecodeError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_unknown_text(value) -> bool:
    text = _clean_text(value)
    if not text:
        return True
    return text.casefold().startswith("unknown")


def extract_company(job: RawJob, raw_context: dict) -> str | None:
    company = _clean_text(getattr(job, "company", None))
    if company and not _is_unknown_text(company):
        return company

    raw_company = _clean_text(raw_context.get("company"))
    if raw_company and not _is_unknown_text(raw_company):
        return raw_company

    return company or raw_company


def extract_direct_topcv_sections(job: RawJob, raw_context: dict) -> dict[str, str | None]:
    """Return the stable, directly-mappable TopCV sections for clean output."""
    structured_description = _clean_text(raw_context.get("description"))
    structured_requirement = _clean_text(raw_context.get("requirements"))
    structured_benefit = _clean_text(raw_context.get("benefits"))

    fallback_source = (
        _clean_text(raw_context.get("info"))
        or _clean_text(getattr(job, "raw_markdown", None))
        or ""
    )
    legacy_description, legacy_requirement, legacy_benefit = LLMProvider._extract_info(fallback_source)

    return {
        "description": structured_description or _clean_text(legacy_description),
        "requirement": structured_requirement or _clean_text(legacy_requirement),
        "benefit": structured_benefit or _clean_text(legacy_benefit),
    }


def extract_location_hint(job_location, raw_context: dict) -> str | None:
    if _clean_text(job_location) and not _is_unknown_text(job_location):
        return _clean_text(job_location)

    work_location = _clean_text(raw_context.get("work_location"))
    if work_location and not _is_unknown_text(work_location):
        return work_location

    return _clean_text(job_location)


def looks_like_internship(*texts: str | None) -> bool:
    for text in texts:
        cleaned = _clean_text(text)
        if not cleaned:
            continue
        lowered = cleaned.casefold()
        if any(hint in lowered for hint in _INTERNSHIP_HINTS):
            return True
    return False


def build_topcv_parser_hints(job: RawJob, raw_context: dict) -> dict[str, str | bool | list[str] | None]:
    """Return deterministic parser hints for fields that are not direct raw facts."""
    location_hint = extract_location_hint(job.location, raw_context)
    is_internship = looks_like_internship(job.title, raw_context.get("title"), raw_context.get("info"), job.raw_markdown)
    cities = [location_hint] if location_hint and not _is_unknown_text(location_hint) else []

    return {
        "location_hint": location_hint,
        "cities": cities,
        "is_internship": is_internship,
    }


def _build_preferred_info_text(raw_context: dict) -> str | None:
    structured_values = {
        field: _clean_text(raw_context.get(field))
        for field in _TOPCV_SECTION_ORDER
    }

    if not any(structured_values.values()):
        return _clean_text(raw_context.get("info"))

    legacy_description, legacy_requirement, legacy_benefit = LLMProvider._extract_info(
        _clean_text(raw_context.get("info")) or ""
    )
    fallback_values = {
        "description": _clean_text(legacy_description),
        "requirements": _clean_text(legacy_requirement),
        "benefits": _clean_text(legacy_benefit),
    }

    sections: list[str] = []
    for field_name in _TOPCV_SECTION_ORDER:
        field_value = structured_values.get(field_name) or fallback_values.get(field_name) or ""
        sections.append(f"{_TOPCV_SECTION_HEADING[field_name]}\n{field_value}")
    return "\n\n".join(sections)


def build_deterministic_processed_job(job: RawJob) -> ProcessedJob:
    raw_context = _safe_load_raw_json_dump(job.full_json_dump)
    sections = extract_direct_topcv_sections(job, raw_context)
    parser_hints = build_topcv_parser_hints(job, raw_context)
    title = _clean_text(job.title) or _clean_text(raw_context.get("title")) or "Unknown"
    company = extract_company(job, raw_context)

    return ProcessedJob(
        standardized_title=title,
        company=company,
        job_level=None,
        is_internship=bool(parser_hints["is_internship"]),
        cities=list(parser_hints["cities"] or []),
        experience=None,
        min_gpa=None,
        english_requirement=None,
        salary_min=None,
        salary_max=None,
        currency="VND",
        is_salary_negotiable=False,
        tech_stack=[],
        technical_competencies=[],
        domain_knowledge=[],
        description=sections["description"],
        requirement=sections["requirement"],
        benefit=sections["benefit"],
    )


def build_llm_job_context(job: RawJob) -> RawJob:
    raw_context = _safe_load_raw_json_dump(job.full_json_dump)
    if not raw_context:
        return job

    updates = {}
    preferred_info = _build_preferred_info_text(raw_context)
    if preferred_info:
        normalized_context = dict(raw_context)
        normalized_context["info"] = preferred_info
        updates["full_json_dump"] = json.dumps(normalized_context, ensure_ascii=False)

    preferred_location = extract_location_hint(job.location, raw_context)
    if preferred_location and preferred_location != job.location:
        updates["location"] = preferred_location

    if not updates:
        return job

    return job.model_copy(update=updates)


class JobProcessor():

    def __init__(self):
        self.router = llm_router
        self.embedder = Embedder()

    def _build_embedding_text(self, parsed_result) -> str:
        """
        Build a rich text representation of the parsed job for embedding.
        """
        parts = []
        if parsed_result.standardized_title:
            parts.append(f"Title: {parsed_result.standardized_title}")
        if parsed_result.job_level:
            parts.append(f"Level: {parsed_result.job_level}")
        if parsed_result.cities:
            parts.append(f"Location: {', '.join(parsed_result.cities)}")
        if parsed_result.description:
            parts.append(parsed_result.description)
        if parsed_result.requirement:
            parts.append(parsed_result.requirement)
        if parsed_result.tech_stack:
            parts.append(f"Tech Stack: {', '.join(parsed_result.tech_stack)}")
        if parsed_result.technical_competencies:
            parts.append(f"Competencies: {', '.join(parsed_result.technical_competencies)}")
        if parsed_result.domain_knowledge:
            parts.append(f"Domain: {', '.join(parsed_result.domain_knowledge)}")
        return "\n".join(parts)

    async def process_jobs(self, limit: int = 100, skip_llm_validation: bool = False, crawl_run_id: str | None = None):
        """Process pending raw jobs through validation, LLM transformation, embedding, and loading.
        
        Async with smart rate limiting: only sleeps the remaining interval after
        accounting for actual LLM processing time.
        
        Returns:
            (success_count, fail_count)
        """
        logger.info(
            "Job processing cycle starting",
            limit=limit,
            skip_llm_validation=skip_llm_validation,
            crawl_run_id=crawl_run_id,
        )
        if skip_llm_validation:
            logger.warning("LLM validation skipped in local/dev mode", limit=limit)

        from src.internhunter.extraction.validator import JobValidator
        validator = None if skip_llm_validation else JobValidator()
        repo = ETLRepository()
        
        # Use new production-grade fetch
        jobs = repo.fetch_pending_raw_jobs(limit=limit, crawl_run_id=crawl_run_id)
        logger.info(
            "Pending raw jobs selected",
            limit=limit,
            crawl_run_id=crawl_run_id,
            count=len(jobs),
            raw_job_ids=[job.id for job in jobs],
            urls=[job.url for job in jobs],
            retry_counts=[job.retry_count for job in jobs],
        )

        success_count = 0
        fail_count = 0

        # Smart rate limiting: only sleep the remaining time after LLM call
        llm_rpm = settings.config_yaml.get("llm", {}).get("rate_limit_rpm", 20)
        min_interval = 60.0 / llm_rpm if llm_rpm > 0 else 0

        for job in jobs:
            iteration_start = time.monotonic()

            try:
                # Step 1: Validation Guardrail (Heuristics + LLM-Lite)
                raw_text = build_validation_text(job)
                if skip_llm_validation:
                    if not JobValidator.heuristic_check(raw_text):
                        is_valid = False
                        reason = "Heuristic check failed: text too short or lacks job keywords."
                    else:
                        is_valid = True
                        reason = "LLM validation skipped in local/dev mode"
                else:
                    is_valid, reason = validator.is_valid(raw_text)
                
                if not is_valid:
                    logger.warning("Job rejected by validator", url=job.url, reason=reason)
                    repo.update_job_status(job.id, "failed")
                    repo.save_to_audit({
                        "url": job.url,
                        "error_type": "VALIDATION_FAILED",
                        "error_message": reason,
                        "html_content": raw_text[:10000] # Store snippet of raw data
                    })
                    fail_count += 1
                    continue

                # Step 2: Parse the job with LLM (Gemini -> Groq fallback)
                job_for_llm = build_llm_job_context(job)
                logger.info("Transforming job", url=job.url, method=job.extraction_method)
                parsed_result = self.router.process_with_fallback(job_for_llm)
                raw_context = _safe_load_raw_json_dump(job.full_json_dump)
                parsed_result = parsed_result.model_copy(
                    update={"company": extract_company(job, raw_context)}
                )
                
                # Step 3: Strict Quality Gate (Post-Parse)
                # Verify critical fields exist
                if not parsed_result.standardized_title or not parsed_result.description:
                    logger.error("LLM failed to extract critical fields", url=job.url)
                    repo.update_job_status(job.id, "failed")
                    repo.save_to_audit({
                        "url": job.url,
                        "error_type": "LLM_INCOMPLETE",
                        "error_message": "Missing critical fields (title/description) in LLM output"
                    })
                    fail_count += 1
                    continue

                # Step 4: Generate embedding from parsed content
                embedding = None
                text_to_embed = self._build_embedding_text(parsed_result)
                if text_to_embed.strip():
                    try:
                        embedding = self.embedder.generate_embedding(text_to_embed)
                        logger.info("Embedding generated", job_title=job.title)
                    except Exception as e:
                        logger.warning("Embedding failed", job_id=job.id, error=str(e))

                # Step 5: Save parsed job + embedding together
                if repo.save_parsed_job(parsed_result, job.id, job.url, embedding=embedding):
                    repo.update_job_status(job.id, "completed")
                    success_count += 1
                    logger.info("Parsed job saved", job_title=job.title, has_embedding=embedding is not None)
                else:
                    repo.update_job_status(job.id, "failed")
                    fail_count += 1
                
            except Exception as e:
                logger.error("Job processing failed", job_id=job.id, error=str(e), exc_info=True)
                repo.update_job_status(job.id, "failed")
                repo.save_to_audit({
                    "url": job.url,
                    "error_type": "PROCESSING_ERROR",
                    "error_message": str(e)
                })
                fail_count += 1

            # Smart rate limiting: only sleep the remaining interval
            elapsed = time.monotonic() - iteration_start
            if min_interval > 0 and elapsed < min_interval:
                sleep_time = min_interval - elapsed
                await asyncio.sleep(sleep_time)

        logger.info("Batch completed", success=success_count, failed=fail_count)
        return success_count, fail_count

    async def process_jobs_deterministic(self, limit: int = 100, crawl_run_id: str | None = None):
        """Process pending raw jobs without any LLM calls.

        This mode is intended for evaluation and regression checks against the
        crawler's structured raw contract. It reuses the normal persistence path
        but skips validation LLM calls, transformation LLM calls, and embedding
        generation.
        """
        logger.info(
            "Deterministic job processing cycle starting",
            limit=limit,
            crawl_run_id=crawl_run_id,
        )

        repo = ETLRepository()
        jobs = repo.fetch_pending_raw_jobs(limit=limit, crawl_run_id=crawl_run_id)
        logger.info(
            "Pending raw jobs selected for deterministic processing",
            limit=limit,
            crawl_run_id=crawl_run_id,
            count=len(jobs),
            raw_job_ids=[job.id for job in jobs],
            urls=[job.url for job in jobs],
        )

        success_count = 0
        fail_count = 0

        for job in jobs:
            try:
                parsed_result = build_deterministic_processed_job(job)
                if repo.save_parsed_job(parsed_result, job.id, job.url, embedding=None):
                    repo.update_job_status(job.id, "completed")
                    success_count += 1
                    logger.info(
                        "Deterministic parsed job saved",
                        job_title=job.title,
                        has_description=bool(parsed_result.description),
                        has_requirement=bool(parsed_result.requirement),
                        has_benefit=bool(parsed_result.benefit),
                    )
                else:
                    repo.update_job_status(job.id, "failed")
                    fail_count += 1
            except Exception as e:
                logger.error("Deterministic job processing failed", job_id=job.id, error=str(e), exc_info=True)
                repo.update_job_status(job.id, "failed")
                repo.save_to_audit({
                    "url": job.url,
                    "error_type": "PROCESSING_ERROR",
                    "error_message": str(e),
                })
                fail_count += 1

        logger.info("Deterministic batch completed", success=success_count, failed=fail_count)
        return success_count, fail_count

async def run_pipeline(limit: int = 10):
    processor = JobProcessor()
    await processor.process_jobs(limit=limit)
