from __future__ import annotations

import json
import re
import unicodedata

from src.core.models import RawJob
from src.internhunter.common.logging import get_logger

logger = get_logger(__name__)

_TOPCV_STRUCTURED_CONTEXT_FIELDS = (
    "description",
    "requirements",
    "benefits",
    "work_location",
    "working_time",
    "application_method",
)


def extract_info(info: str):
    """Extract legacy description, requirements, and benefits from free-form info text."""
    if not info:
        return None, None, None

    info = unicodedata.normalize("NFKC", info)
    flags = re.DOTALL | re.IGNORECASE

    des_pattern = (
        r"(?:M\u00f4 t\u1ea3(?:\s+c\u00f4ng\s+vi\u1ec7c)?|Job\s*(?:Summary|Description))"
        r"(.*?)(?=Y\u00eau c\u1ea7u|Responsibilities|Requirements|$)"
    )
    req_pattern = (
        r"(?:Y\u00eau c\u1ea7u(?:\s+\u1ee9ng\s+vi\u00ean)?|Responsibilities|Requirements)"
        r"(.*?)(?=Quy\u1ec1n l\u1ee3i|Ph\u00fac l\u1ee3i|Benefits|$)"
    )
    ben_pattern = (
        r"(?:Quy\u1ec1n l\u1ee3i(?:\s+\u0111\u01b0\u1ee3c\s+h\u01b0\u1edfng)?|Ph\u00fac l\u1ee3i|Benefits)"
        r"(.*)"
    )

    des_match = re.search(des_pattern, info, flags)
    req_match = re.search(req_pattern, info, flags)
    ben_match = re.search(ben_pattern, info, flags)

    des = des_match.group(1).strip() if des_match else info
    req = req_match.group(1).strip() if req_match else None
    ben = ben_match.group(1).strip() if ben_match else None

    return des, req, ben


def clean_text(value):
    """Normalize a value into stripped text or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def safe_json_dump(value) -> dict:
    """Parse a raw JSON dump into a dictionary, returning an empty dict on failure."""
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_topcv_processing_contract(raw_context: dict, fallback_text: str) -> dict[str, str | None]:
    """Prefer structured TopCV fields, then fall back to legacy info text."""
    structured_values = {
        field: clean_text(raw_context.get(field))
        for field in _TOPCV_STRUCTURED_CONTEXT_FIELDS
    }

    info_source = clean_text(raw_context.get("info")) or clean_text(fallback_text) or ""
    has_structured_sections = any(structured_values.values())
    if has_structured_sections:
        legacy_description, legacy_requirement, legacy_benefit = extract_info(info_source)
        structured_values["description"] = structured_values["description"] or clean_text(legacy_description)
        structured_values["requirements"] = structured_values["requirements"] or clean_text(legacy_requirement)
        structured_values["benefits"] = structured_values["benefits"] or clean_text(legacy_benefit)
        raw_context = dict(raw_context)
        raw_context["info"] = info_source
        for field in _TOPCV_STRUCTURED_CONTEXT_FIELDS:
            if structured_values.get(field) is not None:
                raw_context[field] = structured_values[field]
        return {
            "raw_context": raw_context,
            "description": structured_values["description"],
            "requirement": structured_values["requirements"],
            "benefit": structured_values["benefits"],
            "work_location": structured_values["work_location"],
            "working_time": structured_values["working_time"],
            "application_method": structured_values["application_method"],
        }

    legacy_description, legacy_requirement, legacy_benefit = extract_info(info_source)
    raw_context = dict(raw_context)
    raw_context["info"] = info_source
    return {
        "raw_context": raw_context,
        "description": clean_text(legacy_description),
        "requirement": clean_text(legacy_requirement),
        "benefit": clean_text(legacy_benefit),
        "work_location": clean_text(raw_context.get("work_location")),
        "working_time": clean_text(raw_context.get("working_time")),
        "application_method": clean_text(raw_context.get("application_method")),
    }


def prepare_job_context(job_data: RawJob) -> tuple[dict, str | None, str | None, str | None, str | None, str | None, str | None]:
    """Parse raw job JSON and return the structured TopCV context tuple used by providers."""
    raw_context = {}
    if job_data.full_json_dump:
        try:
            raw_context = (
                job_data.full_json_dump
                if isinstance(job_data.full_json_dump, dict)
                else json.loads(job_data.full_json_dump)
            )
            if not isinstance(raw_context, dict):
                raw_context = {}
        except Exception as e:
            logger.warning(
                "Failed to parse full_json_dump, using empty context",
                url=getattr(job_data, "url", "unknown"),
                error=str(e),
            )
            raw_context = {}

    fallback_text = clean_text(getattr(job_data, "raw_markdown", None)) or ""
    preferred = build_topcv_processing_contract(raw_context, fallback_text)
    return (
        preferred["raw_context"],
        preferred["description"],
        preferred["requirement"],
        preferred["benefit"],
        preferred["work_location"],
        preferred["working_time"],
        preferred["application_method"],
    )
