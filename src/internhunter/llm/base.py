from abc import ABC, abstractmethod

from src.core.models import ProcessedJob, RawJob
from src.internhunter.llm.context import (
    build_topcv_processing_contract,
    clean_text,
    extract_info,
    prepare_job_context,
    safe_json_dump,
)


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    def process_raw_job(self, job_data: RawJob) -> ProcessedJob:
        """Process a raw job posting into structured data using the LLM."""
        ...

    @abstractmethod
    def translate(self, text: str) -> str:
        """Translate text to English."""
        ...

    @staticmethod
    def _extract_info(info: str):
        """Compatibility wrapper for the TopCV legacy-info parser."""
        return extract_info(info)

    @staticmethod
    def _safe_json_dump(value):
        """Compatibility wrapper for JSON parsing of raw TopCV context."""
        return safe_json_dump(value)

    @staticmethod
    def _clean_text(value):
        """Compatibility wrapper for the shared text-normalization helper."""
        return clean_text(value)

    @classmethod
    def _build_topcv_processing_contract(cls, raw_context: dict, fallback_text: str) -> dict[str, str | None]:
        """Compatibility wrapper for the shared TopCV processing contract helper."""
        return build_topcv_processing_contract(raw_context, fallback_text)

    @classmethod
    def _build_preferred_topcv_context(cls, raw_context: dict, fallback_text: str) -> dict[str, str | None]:
        """Backward-compatible alias for the explicit TopCV processing contract."""
        return build_topcv_processing_contract(raw_context, fallback_text)

    def _prepare_job_context(self, job_data: RawJob):
        """Parse raw JSON and return the structured TopCV context tuple used by providers."""
        return prepare_job_context(job_data)
