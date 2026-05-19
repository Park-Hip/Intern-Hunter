"""
Typed result models for the link-fetching stage.

Replaces the ambiguous `list | None` return with a structured outcome
that lets the orchestrator distinguish between "no new jobs" vs "blocked" vs "error".
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


class FetchStatus(Enum):
    """Distinguishes the 4+ ways fetch_job_links can terminate."""
    SUCCESS = "success"
    BLOCKED = "blocked"
    NETWORK_FAIL = "network_fail"
    NO_NEW = "no_new"
    PARSE_ERROR = "parse_error"


@dataclass
class FetchOutcome:
    """Structured result from the link-fetching stage.

    Attributes:
        status: Why the fetch ended.
        links: New, deduplicated links (only present on SUCCESS).
        total_scraped: Total links found across all pages before dedup.
        pages_scraped: Number of search result pages successfully scraped.
        error: Human-readable error message (on failure statuses).
    """
    status: FetchStatus
    links: Optional[List[Dict]] = field(default_factory=list)
    total_scraped: int = 0
    pages_scraped: int = 0
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.status == FetchStatus.SUCCESS

    @property
    def new_count(self) -> int:
        return len(self.links) if self.links else 0
