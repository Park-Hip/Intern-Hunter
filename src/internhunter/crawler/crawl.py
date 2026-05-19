import asyncio
import base64
import hashlib
import html as html_lib
import json
import os
import random
import re
import time
import uuid
import unicodedata
from datetime import datetime, timezone

from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.internhunter.config.settings import settings
from src.core.utils import normalize_url
from src.core.models.fetch_result import FetchOutcome, FetchStatus
from src.core.models.extraction_result import ExtractionResult
from src.internhunter.storage.repositories.etl import ETLRepository
from src.internhunter.common.logging import get_logger, configure_logging, bind_context, clear_context
from src.internhunter.crawler.crawl_config import (
    build_browser_config,
    build_fetch_link_run_config,
    build_extract_detail_run_config
)

from crawl4ai import AsyncWebCrawler
from crawl4ai.browser_adapter import UndetectedAdapter

logger = get_logger(__name__)

# Retry on transient network/IO errors only (do not retry on block/captcha - those are in result)
RETRY_EXCEPTIONS = (ConnectionError, OSError, asyncio.TimeoutError, TimeoutError)

BLOCKED_PAGE_PHRASES = (
    "Verify you are human",
    "Just a moment",
    "Please enable cookies",
    "Sorry, you have been blocked",
    "You are unable to access topcv.vn",
    "Cloudflare Ray ID",
    "Performance & security by",
)

_TIMEOUT_PHRASES = (
    "timeout",
    "timed out",
    "time out",
    "deadline exceeded",
)

_BROWSER_ERROR_PHRASES = (
    "browser",
    "page crashed",
    "crashed",
    "closed",
    "target closed",
    "context closed",
)

_NETWORK_ERROR_PHRASES = (
    "network",
    "dns",
    "connection reset",
    "connection refused",
    "connection aborted",
    "host unreachable",
)

_NAVIGATION_ERROR_PHRASES = (
    "navigation",
    "navigat",
    "load failed",
    "goto",
    "page.goto",
    "wait for selector",
)

# Small buffer so a local `--limit N` crawl can still return up to N eligible URLs
# after recently-blocked URLs are filtered out.
RECENT_BLOCKED_OVERFETCH_BUFFER = 3

TOPCV_SECTION_HEADING_ALIASES = {
    "description": ("Mô tả công việc",),
    "requirements": ("Yêu cầu ứng viên",),
    "benefits": ("Quyền lợi", "Quyền lợi được hưởng"),
    "work_location": ("Địa điểm làm việc",),
    "working_time": ("Thời gian làm việc",),
}

TOPCV_SECTION_EXTRACTION_PRIORITY = (

    "description",
    "requirements",
    "benefits",
    "work_location",
    "working_time",
)

TOPCV_EXTRACTION_VERSION = "topcv_section_v2"

TOPCV_SECTION_SOURCE_LABELS = (
    ("info_text", "css_selected_job_content"),
    ("raw_markdown", "raw_markdown"),
    ("html_text", "html_text"),
)


def _extract_raw_markdown(result) -> str | None:
    """Compatibility helper for crawl4ai markdown result shapes."""
    markdown_result = getattr(result, "markdown", None)
    if markdown_result is None:
        markdown_result = getattr(result, "markdown_v2", None)

    if markdown_result is None:
        return None

    if isinstance(markdown_result, str):
        return markdown_result

    return getattr(markdown_result, "raw_markdown", None)


def _normalize_section_source(text: str | None) -> str:
    """Normalize a section source into stable, searchable plain text."""
    if not text:
        return ""

    normalized = html_lib.unescape(str(text))
    normalized = unicodedata.normalize("NFKC", normalized)
    normalized = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", normalized)
    normalized = re.sub(r"(?i)<br\s*/?>", "\n", normalized)
    normalized = re.sub(r"(?i)</(p|div|li|h[1-6]|section|article|tr|td|th|ul|ol)>", "\n", normalized)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    return " ".join(normalized.split())


def _extract_section_from_source(text: str | None, section_name: str) -> str | None:
    """Extract one TopCV section from normalized source text if the heading exists."""
    normalized = _normalize_section_source(text)
    if not normalized:
        return None

    normalized_cf = normalized.casefold()
    heading_aliases = TOPCV_SECTION_HEADING_ALIASES.get(section_name, ())
    if not heading_aliases:
        return None

    heading_matches: list[tuple[int, str]] = []
    for alias in heading_aliases:
        alias_normalized = _normalize_section_source(alias)
        if not alias_normalized:
            continue
        index = normalized_cf.find(alias_normalized.casefold())
        if index != -1:
            heading_matches.append((index, alias_normalized))

    if not heading_matches:
        return None

    start_index, matched_heading = min(heading_matches, key=lambda item: item[0])
    end_index = len(normalized)

    for other_section, aliases in TOPCV_SECTION_HEADING_ALIASES.items():
        for alias in aliases:
            alias_normalized = _normalize_section_source(alias)
            if not alias_normalized:
                continue
            if other_section == section_name and alias_normalized == matched_heading:
                continue
            search_index = normalized_cf.find(alias_normalized.casefold(), start_index + len(matched_heading))
            if search_index != -1 and search_index < end_index:
                end_index = search_index

    section_text = normalized[start_index + len(matched_heading):end_index].strip(" \n\r\t:-â€“â€”")
    section_text = " ".join(section_text.split())
    return section_text or None


def _derive_topcv_section_fields_with_provenance(
    *,
    raw_markdown: str | None = None,
    info_text: str | None = None,
    html_text: str | None = None,
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    """Derive TopCV section fields and record which source supplied each value."""
    # Prefer the CSS-selected job-content container text first, then markdown,
    # then any remaining text fallback. This keeps the section slicer anchored
    # on the most layout-specific source available without changing the HTML
    # fallback behavior.
    sources = TOPCV_SECTION_SOURCE_LABELS
    sections: dict[str, str | None] = {}
    section_sources: dict[str, str | None] = {}
    for section_name in TOPCV_SECTION_EXTRACTION_PRIORITY:
        extracted = None
        source_label = None
        for candidate_name, candidate_label in sources:
            candidate_text = {
                "info_text": info_text,
                "raw_markdown": raw_markdown,
                "html_text": html_text,
            }.get(candidate_name)
            extracted = _extract_section_from_source(candidate_text, section_name)
            if extracted:
                source_label = candidate_label
                break
        sections[section_name] = extracted
        section_sources[section_name] = source_label
    return sections, section_sources


def _derive_topcv_section_fields(
    *,
    raw_markdown: str | None = None,
    info_text: str | None = None,
    html_text: str | None = None,
) -> dict[str, str | None]:
    """Derive TopCV section fields without returning source provenance."""
    sections, _ = _derive_topcv_section_fields_with_provenance(
        raw_markdown=raw_markdown,
        info_text=info_text,
        html_text=html_text,
    )
    return sections


def _is_blocked_page(text: str | None) -> bool:
    """Return True when page text contains common TopCV blocking phrases."""
    if not text:
        return False
    return any(phrase.lower() in text.lower() for phrase in BLOCKED_PAGE_PHRASES)


def _classify_fetch_error(error_message: str | None) -> str:
    """Map a fetch error string to the crawler's stable failure taxonomy."""
    return _classify_crawl4ai_failure(error_message)


def _has_navigation_indicator(text: str) -> bool:
    """Return True when an error message looks like a navigation failure."""
    return any(phrase in text for phrase in _NAVIGATION_ERROR_PHRASES)


def _classify_crawl4ai_failure(error_message: str | None) -> str:
    """Classify a Crawl4AI failure message into a normalized failure reason."""
    text = (error_message or "").lower()
    if not text:
        return "unknown_crawl_error"
    # Navigation/page.goto failures should win even when the message also contains "timeout".
    if _has_navigation_indicator(text):
        return "navigation_error"
    if any(phrase in text for phrase in _TIMEOUT_PHRASES):
        return "crawl_timeout"
    if any(phrase in text for phrase in _BROWSER_ERROR_PHRASES):
        return "browser_error"
    if any(phrase in text for phrase in _NETWORK_ERROR_PHRASES):
        return "network_error"
    if any(phrase.lower() in text for phrase in BLOCKED_PAGE_PHRASES):
        return "blocked_or_empty_content"
    if any(phrase in text for phrase in ("parse", "json", "unparseable")):
        return "parse_error"
    if any(phrase in text for phrase in ("empty extraction", "no content", "extraction failed", "empty_extraction")):
        return "empty_extraction"
    return "unknown_crawl_error"


def _audit_crawl_failure(
    repo: ETLRepository,
    url: str,
    error_message: str | None,
    crawl_run_id: str | None = None,
    source_seed_url: str | None = None,
    screenshot_path: str | None = None,
    html_content: str | None = None,
) -> None:
    """Persist a crawl failure row with normalized error metadata."""
    reason = _classify_fetch_error(error_message)
    repo.save_to_audit({
        "url": url,
        "crawl_run_id": crawl_run_id,
        "source_seed_url": source_seed_url,
        "error_type": "CRAWL_FAILED" if reason != "blocked_or_empty_content" else "BOT_DETECTED",
        "error_message": reason,
        "screenshot_path": screenshot_path,
        "html_content": html_content,
    })


def _audit_crawl_skipped(
    repo: ETLRepository,
    url: str,
    error_message: str,
    crawl_run_id: str | None = None,
    source_seed_url: str | None = None,
) -> None:
    """Persist an audit row when a URL is skipped before crawling."""
    repo.save_to_audit({
        "url": url,
        "crawl_run_id": crawl_run_id,
        "source_seed_url": source_seed_url,
        "error_type": "CRAWL_SKIPPED",
        "error_message": error_message,
    })


class Crawler:
    """TopCV crawler responsible for link discovery, detail extraction, and audit writes."""

    def __init__(self, blocked_cooldown_minutes: int | None = None):
        """Initialize crawl timing, cooldown, and run-state settings."""
        self.search_urls = settings.search_urls
        self.max_pages = settings.crawler.max_pages
        topcv_settings = settings.crawler.topcv
        self.detail_delay_min_seconds = topcv_settings.detail_delay_min_seconds
        self.detail_delay_max_seconds = topcv_settings.detail_delay_max_seconds
        self.blocked_delay_min_seconds = topcv_settings.blocked_delay_min_seconds
        self.blocked_delay_max_seconds = topcv_settings.blocked_delay_max_seconds
        self.blocked_early_stop_threshold = topcv_settings.blocked_early_stop_threshold
        self.blocked_cooldown_minutes = (
            blocked_cooldown_minutes
            if blocked_cooldown_minutes is not None
            else topcv_settings.blocked_cooldown_minutes
        )
        self._last_fetch_failure_reason = None
        self._last_fetch_failure_message = None
        self._crawl_session_id = None
        self._blocked_detail_count_in_run = 0

    @staticmethod
    def _session_id_for_run(run_id: str) -> str:
        """Return the deterministic Crawl4AI session id for a crawl run."""
        return f"topcv-{run_id}"

    async def _arun_with_retry(self, crawler, url, config, max_attempts=None):
        """Call crawler.arun with exponential backoff. Raises after max_attempts on network/IO errors."""
        if max_attempts is None:
            max_attempts = settings.crawler.max_retries
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=4, max=60),
            retry=retry_if_exception_type(RETRY_EXCEPTIONS),
            reraise=True,
        ):
            with attempt:
                return await crawler.arun(url=url, config=config)

    async def _fetch_single_page(
        self,
        crawler,
        url: str,
        source_seed_url: str | None = None,
    ) -> tuple[list[dict], FetchStatus | None]:
        """Fetch links from a single search result page.
        
        Returns:
            (links, error_status) â€” links found on this page, and an error status if something went wrong.
            If error_status is not None, the caller should stop pagination.
        """
        await asyncio.sleep(random.uniform(2, 4))

        try:
            fetch_config = build_fetch_link_run_config(self._crawl_session_id)
            result = await self._arun_with_retry(crawler, url, fetch_config)
        except Exception as e:
            logger.error("Network error fetching page", phase="fetch_links", url=url, error=str(e))
            self._last_fetch_failure_reason = "network_error"
            self._last_fetch_failure_message = str(e)
            return [], FetchStatus.NETWORK_FAIL

        if not result.success:
            failure_message = getattr(result, "error_message", None)
            html = getattr(result, "html", None)
            if _is_blocked_page(html):
                failure_reason = "blocked_or_empty_content"
                failure_status = FetchStatus.BLOCKED
            else:
                failure_reason = _classify_fetch_error(failure_message)
                failure_status = FetchStatus.NETWORK_FAIL
            self._last_fetch_failure_reason = failure_reason
            self._last_fetch_failure_message = failure_message
            logger.error(
                "Crawl failed for page",
                phase="fetch_links",
                url=url,
                error=failure_message,
                failure_reason=failure_reason,
            )
            return [], failure_status

        # Check for bot blocking
        if _is_blocked_page(result.html):
            logger.warning("Blocked by captcha/verification", phase="fetch_links", status="block", url=url)
            self._last_fetch_failure_reason = "blocked_or_empty_content"
            self._last_fetch_failure_message = getattr(result, "error_message", None)
            return [], FetchStatus.BLOCKED

        # Parse extracted content with guard
        try:
            data = json.loads(result.extracted_content or "[]")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse extracted content", phase="fetch_links",
                         error=str(e), content_preview=str(result.extracted_content)[:200])
            self._last_fetch_failure_reason = "parse_error"
            self._last_fetch_failure_message = str(e)
            return [], FetchStatus.PARSE_ERROR

        if not isinstance(data, list) or not data:
            logger.info("No links found on page", phase="fetch_links", url=url)
            return [], None  # Empty page = end of pagination, not an error

        # Normalize URLs
        page_links = []
        for item in data:
            raw_url = item.get("url") or ""
            normalized = normalize_url(raw_url)
            if normalized:
                page_links.append({
                    "url": normalized,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "source": "topcv",
                    "source_seed_url": source_seed_url or url,
                })

        return page_links, None

    def _format_fetch_failure_error(self) -> str | None:
        """Combine the last fetch reason and message into a single error string."""
        reason = self._last_fetch_failure_reason
        message = self._last_fetch_failure_message
        if not reason and not message:
            return None
        if reason and message and message != reason:
            return f"{reason}: {message}"
        return reason or message

    def _filter_recently_blocked_links(self, repo: ETLRepository, links: list[dict]) -> tuple[list[dict], set[str]]:
        """Remove URLs that were blocked recently enough to still be in cooldown."""
        candidate_urls = [link.get("url") for link in links if link.get("url")]
        blocked_urls = repo.get_recently_blocked_urls(
            candidate_urls,
            cooldown_minutes=self.blocked_cooldown_minutes,
        )
        eligible_links = [link for link in links if link.get("url") not in blocked_urls]
        return eligible_links, blocked_urls

    async def _apply_detail_crawl_delay(self) -> None:
        """Sleep for the configured crawl delay before the next detail page."""
        if self._blocked_detail_count_in_run > 0:
            delay_range = (self.blocked_delay_min_seconds, self.blocked_delay_max_seconds)
        else:
            delay_range = (self.detail_delay_min_seconds, self.detail_delay_max_seconds)
        delay = random.uniform(*delay_range)
        logger.info(
            "Waiting before extraction",
            delay_seconds=round(delay, 1),
            blocked_count_in_run=self._blocked_detail_count_in_run,
        )
        await asyncio.sleep(delay)

    async def fetch_job_links(self, run_id: str, limit: int | None = None, force_recrawl: bool = False) -> FetchOutcome:
        """Fetches job URLs from all configured search pages with pagination.

        Iterates through the configured TopCV search URLs in priority order and
        paginates each one up to max_pages. Returns a typed FetchOutcome so the
        caller can distinguish between blocked/error/empty/success states.
        """
        bind_context(run_id=run_id)
        logger.info("Fetch links phase starting", phase="fetch_links", status="start",
                    search_urls=len(self.search_urls), max_pages=self.max_pages)
        if force_recrawl:
            logger.warning("Force-recrawl mode enabled for link discovery", phase="fetch_links", run_id=run_id)

        all_links = []
        total_pages_scraped = 0
        last_error_status = None
        reached_limit = False
        candidate_fetch_limit = None if limit is None else limit + RECENT_BLOCKED_OVERFETCH_BUFFER
        self._last_fetch_failure_reason = None
        self._last_fetch_failure_message = None
        self._crawl_session_id = self._session_id_for_run(run_id)

        try:
            async with AsyncWebCrawler(config=build_browser_config(self._crawl_session_id)) as crawler:
                for base_url in self.search_urls:
                    logger.info("Scraping search URL", phase="fetch_links", base_url=base_url)

                    for page in range(1, self.max_pages + 1):
                        # Build paginated URL
                        page_url = f"{base_url}&page={page}" if page > 1 else base_url
                        logger.info("Fetching page", phase="fetch_links", url=page_url, page=page)

                        page_links, error_status = await self._fetch_single_page(crawler, page_url, source_seed_url=base_url)

                        if error_status is not None:
                            last_error_status = error_status
                            logger.warning("Stopping pagination for URL", phase="fetch_links",
                                           base_url=base_url, reason=error_status.value, page=page)
                            break  # Stop paginating this URL, move to next

                        if not page_links:
                            logger.info("No more results, stopping pagination", phase="fetch_links",
                                        base_url=base_url, page=page)
                            break  # Empty page = no more results

                        all_links.extend(page_links)
                        total_pages_scraped += 1
                        logger.info("Page scraped", phase="fetch_links", page=page,
                                    links_on_page=len(page_links), total_so_far=len(all_links))

                        if candidate_fetch_limit is not None and len(all_links) >= candidate_fetch_limit:
                            reached_limit = True
                            logger.info(
                                "Fetch links limit reached",
                                phase="fetch_links",
                                limit=limit,
                                candidate_fetch_limit=candidate_fetch_limit,
                                total_so_far=len(all_links),
                            )
                            break

                    if reached_limit:
                        break

            # Dedup against database unless the caller explicitly requested a dev-only recrawl.
            if not all_links:
                status = last_error_status or FetchStatus.NO_NEW
                logger.info("Fetch links completed with no links", phase="fetch_links",
                            status=status.value, pages_scraped=total_pages_scraped)
                return FetchOutcome(
                    status=status,
                    pages_scraped=total_pages_scraped,
                    error=self._format_fetch_failure_error() if status != FetchStatus.NO_NEW else None,
                )

            if force_recrawl:
                new_links = all_links
            else:
                repo = ETLRepository()
                new_links = repo.filter_new_links(all_links)

            logger.info("Links filtered", phase="fetch_links",
                        total_scraped=len(all_links), new=len(new_links),
                        pages_scraped=total_pages_scraped)

            if new_links:
                repo = ETLRepository()
                eligible_links, blocked_urls = self._filter_recently_blocked_links(repo, new_links)
            else:
                eligible_links, blocked_urls = [], set()

            recently_blocked_filtered_count = len(new_links) - len(eligible_links)
            returned_links = eligible_links[:limit] if limit is not None else eligible_links

            logger.info(
                "Eligible links computed",
                phase="fetch_links",
                candidate_links=len(all_links),
                deduped_links=len(new_links),
                recently_blocked_filtered=recently_blocked_filtered_count,
                eligible_links=len(eligible_links),
                returned_links=len(returned_links),
                pages_scraped=total_pages_scraped,
            )

            if limit is not None and len(returned_links) < limit:
                logger.warning(
                    "Fewer eligible links than requested limit after cooldown filtering",
                    phase="fetch_links",
                    requested_limit=limit,
                    candidate_links=len(all_links),
                    deduped_links=len(new_links),
                    recently_blocked_filtered=recently_blocked_filtered_count,
                    eligible_links=len(eligible_links),
                    returned_links=len(returned_links),
                    pages_scraped=total_pages_scraped,
                )

            if not returned_links:
                if recently_blocked_filtered_count > 0:
                    logger.info(
                        "No eligible links after recently-blocked cooldown filtering",
                        phase="fetch_links",
                        candidate_links=len(all_links),
                        deduped_links=len(new_links),
                        recently_blocked_filtered=recently_blocked_filtered_count,
                        blocked_urls=len(blocked_urls),
                        pages_scraped=total_pages_scraped,
                    )
                return FetchOutcome(
                    status=FetchStatus.NO_NEW,
                    total_scraped=len(all_links),
                    pages_scraped=total_pages_scraped,
                    error=self._format_fetch_failure_error() if last_error_status is not None else None,
                )

            return FetchOutcome(
                status=FetchStatus.SUCCESS,
                links=returned_links,
                total_scraped=len(all_links),
                pages_scraped=total_pages_scraped,
                error=self._format_fetch_failure_error() if last_error_status is not None else None,
            )

        except Exception as e:
            logger.error("Fetch links exception", phase="fetch_links", status="error",
                         error=str(e), exc_info=True)
            return FetchOutcome(status=FetchStatus.NETWORK_FAIL, error=str(e))

        finally:
            self._crawl_session_id = None
            clear_context()


    async def extract_single_job(self, crawler: AsyncWebCrawler, url: str) -> ExtractionResult | None:
        """Extract a single job page. Returns typed ExtractionResult or None on total failure."""
        try:
            detail_config = build_extract_detail_run_config(self._crawl_session_id)
            result = await self._arun_with_retry(crawler, url, detail_config)

            if not result.success:
                failure_reason = _classify_crawl4ai_failure(getattr(result, "error_message", None))
                self._last_extract_failure_reason = failure_reason
                self._last_extract_failure_message = getattr(result, "error_message", None)
                logger.error(
                    "Network/crawl failed",
                    url=url,
                    error=getattr(result, "error_message", None),
                    failure_reason=failure_reason,
                )
                return None

            # 1. Try CSS extraction
            data = None
            if result.extracted_content:
                try:
                    data = json.loads(result.extracted_content)
                    if isinstance(data, list) and data:
                        data = data[0]
                except Exception:
                    data = None

            # Check if CSS extraction was successful and high quality
            css_fields = ['title', 'company', 'salary', 'location', 'experience', 'info']
            is_valid_css = (
                isinstance(data, dict) and 
                data.get('title') and 
                data.get('info') and 
                len(str(data.get('info'))) > 200
            )
            
            if is_valid_css:
                found = [k for k in css_fields if data.get(k)]
                missing = [k for k in css_fields if not data.get(k)]
                enriched_data = dict(data)
                section_fields, section_sources = _derive_topcv_section_fields_with_provenance(
                    raw_markdown=_extract_raw_markdown(result),
                    info_text=str(data.get("info") or ""),
                    html_text=getattr(result, "html", None) or getattr(result, "cleaned_html", None),
                )
                for field_name, field_value in section_fields.items():
                    if field_value and not enriched_data.get(field_name):
                        enriched_data[field_name] = field_value
                enriched_data["extraction_version"] = TOPCV_EXTRACTION_VERSION
                # section_sources is audit/report metadata only: it records which
                # source won for each TopCV section (CSS-selected content, raw
                # markdown, HTML text, or missing) and must not affect crawl behavior.
                enriched_data["section_sources"] = section_sources
                logger.info("CSS extraction successful", url=url,
                            fields_found=",".join(found), fields_missing=",".join(missing))
                return ExtractionResult(
                    url=url,
                    title=data.get('title', '').strip(),
                    company=data.get('company', '').strip(),
                    location=data.get('location', '').strip(),
                    full_json_dump=enriched_data,
                    extraction_method="css",
                    status="pending",
                    raw_markdown=_extract_raw_markdown(result),
                    html=getattr(result, "html", None) or getattr(result, "cleaned_html", None),
                    screenshot=getattr(result, "screenshot", None),
                )
            else:
                # 2. Fallback to RAW Markdown
                logger.warning("CSS extraction failed/poor quality, using RAW fallback", url=url)
                
                html = (result.html or "")
                is_blocked = _is_blocked_page(html)
                blocked_reason = None
                if is_blocked:
                    blocked_reason = "blocked_or_empty_content"
                elif not data:
                    blocked_reason = "empty_or_unparseable_css_content"
                
                return ExtractionResult(
                    url=url,
                    title="Unknown (RAW)",
                    company="Unknown (RAW)",
                    location="Unknown",
                    raw_markdown=_extract_raw_markdown(result),
                    extraction_method="raw",
                    status="blocked" if is_blocked else "pending",
                    screenshot=result.screenshot,
                    html=result.html,
                    full_json_dump={
                        "error": "CSS extraction failed",
                        "is_blocked": is_blocked,
                        "blocked_reason": blocked_reason,
                    }
                )

        except Exception as e:
            logger.error("Extraction error", url=url, error=str(e), exc_info=True)
            return None

    def _save_screenshot(self, screenshot_b64: str | None, url: str) -> str | None:
        """Save a base64 screenshot to disk for debugging blocked pages."""
        if not screenshot_b64:
            return None
        try:
            safe_id = hashlib.md5(url.encode()).hexdigest()
            errors_dir = settings.BASE_DIR / "errors"
            os.makedirs(errors_dir, exist_ok=True)
            img_path = str(errors_dir / f"error_{safe_id}_{int(time.time())}.png")
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(screenshot_b64))
            return img_path
        except Exception as e:
            logger.warning("Failed to save screenshot", error=str(e))
            return None

    async def crawl_jobs(self, new_links, run_id: str, force_recrawl: bool = False) -> tuple[int, int]:
        """Crawl new_links fetched by fetch_job_links().
        
        Returns:
            (saved_count, failed_count) so the flow can record extraction telemetry.
        """
        self._crawl_session_id = self._session_id_for_run(run_id)
        bind_context(run_id=run_id)
        try:
            if not new_links:
                logger.error("Extract phase skipped", phase="extract", status="skip", reason="no_links")
                return 0, 0
            if force_recrawl:
                logger.warning("Force-recrawl mode enabled for job crawling", phase="extract", run_id=run_id)

            repo = ETLRepository()
            raw_jobs_count = repo.get_raw_jobs_count()
            # Defensive re-check: links may have been saved by a concurrent pipeline run
            # between fetch_job_links() and crawl_jobs(). Safe to keep unless force-recrawl was explicitly requested.
            if force_recrawl:
                remaining_links = new_links
            else:
                remaining_links = repo.filter_new_links(new_links)

            new_links_count = len(new_links)
            already_in_db = new_links_count - len(remaining_links)
            blocked_urls = repo.get_recently_blocked_urls(
                [link["url"] for link in remaining_links],
                cooldown_minutes=self.blocked_cooldown_minutes,
            )
            if force_recrawl and blocked_urls:
                logger.info(
                    "Force-recrawl still respecting recently blocked cooldown",
                    phase="extract",
                    blocked_urls=len(blocked_urls),
                    cooldown_minutes=self.blocked_cooldown_minutes,
                )

            logger.info(
                "Extract phase starting",
                phase="extract",
                status="start",
                db_raw_jobs=raw_jobs_count,
                links_from_file=new_links_count,
                already_in_db=already_in_db,
                remaining=len(remaining_links)
            )

            if not remaining_links:
                logger.info("Extract phase completed", phase="extract", status="done", reason="no_remaining_links")
                return 0, 0

            start_time = time.monotonic()
            saved_count = 0
            failed_count = 0
            skipped_count = 0
            stopped_early = False

            adapter = UndetectedAdapter()
            async with AsyncWebCrawler(config=build_browser_config(self._crawl_session_id), browser_adapter=adapter) as crawler:
                for i, link_record in enumerate(remaining_links):
                    if self._blocked_detail_count_in_run >= self.blocked_early_stop_threshold:
                        stopped_early = True
                        logger.warning(
                            "Stopping crawl early due to repeated blocked pages",
                            phase="extract",
                            blocked_count_in_run=self._blocked_detail_count_in_run,
                            stop_threshold=self.blocked_early_stop_threshold,
                            remaining_unattempted=len(remaining_links) - i,
                        )
                        break

                    url = link_record["url"]
                    source_seed_url = link_record.get("source_seed_url")
                    # Force-recrawl intentionally bypasses dedup, but we still respect the
                    # recent-blocked cooldown so local retries do not keep hammering TopCV.
                    if url in blocked_urls:
                        skipped_count += 1
                        logger.warning(
                            "Skipping recently blocked URL due to cooldown",
                            phase="extract",
                            url=url,
                            cooldown_minutes=self.blocked_cooldown_minutes,
                            reason="recently_blocked_cooldown",
                        )
                        _audit_crawl_skipped(
                            repo,
                            url,
                            "recently_blocked_cooldown",
                            crawl_run_id=run_id,
                            source_seed_url=source_seed_url,
                        )
                        continue
                    await self._apply_detail_crawl_delay()
                    self._last_extract_failure_reason = None
                    self._last_extract_failure_message = None
                    logger.info(
                        "Processing job",
                        phase="extract",
                        progress=f"{i + 1}/{len(remaining_links)}",
                        url=url
                    )

                    extraction = await self.extract_single_job(crawler, url)

                    if extraction:
                        job_to_save = extraction.to_save_dict()
                        job_to_save["crawl_run_id"] = run_id
                        job_to_save["source_seed_url"] = source_seed_url
                        job_to_save["html_content"] = extraction.html
                        job_to_save["screenshot_path"] = self._save_screenshot(extraction.screenshot, url)

                        if extraction.status == "blocked":
                            self._blocked_detail_count_in_run += 1

                        if repo.save_raw_job(job_to_save):
                            saved_count += 1
                            
                            # Handle immediate audit if blocked
                            if extraction.status == "blocked":
                                _audit_crawl_failure(
                                    repo,
                                    url,
                                    "Sorry, you have been blocked",
                                    crawl_run_id=run_id,
                                    source_seed_url=source_seed_url,
                                    screenshot_path=job_to_save["screenshot_path"],
                                    html_content=extraction.html,
                                )
                        else:
                            failed_count += 1
                            logger.warning("Database save failed", phase="extract", url=url, status="db_fail")

                    else:
                        failed_count += 1
                        failure_reason = self._last_extract_failure_reason or "unknown_crawl_error"
                        failure_message = self._last_extract_failure_message
                        logger.info(
                            "Extraction failed completely",
                            phase="extract",
                            url=url,
                            status="extract_fail",
                            failure_reason=failure_reason,
                            crawl4ai_error=failure_message,
                        )
                        _audit_crawl_failure(
                            repo,
                            url,
                            failure_reason,
                            crawl_run_id=run_id,
                            source_seed_url=source_seed_url,
                        )
                        if failure_reason == "blocked_or_empty_content":
                            self._blocked_detail_count_in_run += 1

            duration_sec = time.monotonic() - start_time
            logger.info(
                "Extract phase completed",
                phase="extract",
                status="done",
                total=len(remaining_links),
                saved=saved_count,
                failed=failed_count,
                skipped=skipped_count,
                blocked_count_in_run=self._blocked_detail_count_in_run,
                stopped_early=stopped_early,
                duration_sec=round(duration_sec, 1)
            )
            return saved_count, failed_count
        finally:
            self._crawl_session_id = None
            self._blocked_detail_count_in_run = 0
            clear_context()
        


async def run_crawler_pipeline(run_id: str):
    """Run the crawl-only pipeline for a single run id."""
    crawler = Crawler()
    outcome = await crawler.fetch_job_links(run_id)
    if outcome.is_success and outcome.links:
        await crawler.crawl_jobs(outcome.links, run_id)


if __name__ == "__main__":

    configure_logging()
    
    run_id = str(uuid.uuid4())[:8]
    logger.info("Crawler pipeline starting", run_id=run_id)

    asyncio.run(run_crawler_pipeline(run_id))
