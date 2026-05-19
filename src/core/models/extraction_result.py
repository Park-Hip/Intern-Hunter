"""
Typed result model for the detail-extraction stage.

Replaces raw dict passing between extract_single_job() → crawl_jobs() → save_raw_job()
with a typed dataclass to prevent typo/drift bugs.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ExtractionResult:
    """Structured output from extract_single_job().

    Attributes:
        url: The canonical URL that was scraped.
        title: Job title (from CSS) or "Unknown (RAW)" on fallback.
        company: Company name (from CSS) or "Unknown (RAW)" on fallback.
        location: Location string (from CSS) or "Unknown" on fallback.
        full_json_dump: Complete CSS extraction result dict (or error dict on fallback).
        extraction_method: "css" or "raw".
        status: "pending" or "blocked".
        raw_markdown: Full page markdown (only on RAW fallback).
        screenshot: Base64 screenshot (only on RAW fallback).
        html: Raw HTML (only on RAW fallback, for audit).
    """
    url: str
    title: str
    company: str
    location: str
    full_json_dump: dict
    extraction_method: str  # "css" | "raw"
    status: str = "pending"  # "pending" | "blocked"
    raw_markdown: Optional[str] = None
    screenshot: Optional[str] = None
    html: Optional[str] = None

    def to_save_dict(self) -> dict[str, Any]:
        """Convert to the dict format expected by ETLRepository.save_raw_job()."""
        return {
            "url": self.url,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "full_json_dump": self.full_json_dump,
            "status": self.status,
            "extraction_method": self.extraction_method,
            "raw_markdown": self.raw_markdown,
        }
