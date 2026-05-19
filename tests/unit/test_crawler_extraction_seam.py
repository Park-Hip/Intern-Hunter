import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.models.fetch_result import FetchStatus
from src.internhunter.crawler.crawl import (
    Crawler,
    TOPCV_EXTRACTION_VERSION,
    _classify_fetch_error,
    _derive_topcv_section_fields,
    _derive_topcv_section_fields_with_provenance,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "topcv"
TOPCV_CRAWL_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "crawl_samples" / "topcv"


class MockCrawlResult:
    def __init__(self, html: str, extracted_content: str, markdown: str):
        self.success = True
        self.error_message = None
        self.extracted_content = extracted_content
        self.html = html
        self.markdown = SimpleNamespace(raw_markdown=markdown)
        self.screenshot = None


class DummyAsyncWebCrawler:
    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyExtraction:
    def __init__(self, url: str):
        self.status = "pending"
        self.screenshot = None
        self.html = f"<html><body>{url}</body></html>"
        self._url = url

    def to_save_dict(self):
        return {
            "url": self._url,
            "title": "Title",
            "company": "Company",
            "location": "Location",
            "full_json_dump": {"title": "Title"},
            "status": self.status,
            "extraction_method": "css",
            "raw_markdown": None,
        }


def _load_exported_topcv_fixture(run_id: str = "fb750e62") -> tuple[str, str]:
    run_dir = TOPCV_CRAWL_FIXTURE_DIR / run_id
    job_dir = next(path for path in run_dir.iterdir() if path.is_dir())
    raw_html = (job_dir / "raw.html").read_text(encoding="utf-8")
    raw_markdown = (job_dir / "raw_markdown.txt").read_text(encoding="utf-8")
    return raw_html, raw_markdown


@pytest.fixture(autouse=True)
def _no_crawler_sleep(mocker):
    async def _sleep(*args, **kwargs):
        return None

    mocker.patch("src.internhunter.crawler.crawl.asyncio.sleep", side_effect=_sleep)


def _make_fetch_result(*, success: bool, error_message: str | None, html: str, extracted_content: str | None = None):
    return SimpleNamespace(
        success=success,
        error_message=error_message,
        html=html,
        extracted_content=extracted_content,
        markdown=SimpleNamespace(raw_markdown=None),
        screenshot=None,
    )


@pytest.mark.asyncio
async def test_extract_single_job_returns_pending_raw_extraction_for_normal_topcv_fixture(mocker):
    html = (FIXTURE_DIR / "normal_job.html").read_text(encoding="utf-8")
    raw_markdown = "This is representative markdown for a TopCV job detail page."
    extracted_content = json.dumps([
        {
            "title": "Software Engineer Test",
            "company": "Boundary Co",
            "salary": "Negotiable",
            "location": "Hanoi, Vietnam",
            "experience": "2 years",
            "info": (
                "This is a representative TopCV-like job detail page used for fixture-based extraction tests. "
                "It includes responsibilities, requirements, and benefits sections. "
                "The content is intentionally long enough to satisfy the crawler's CSS quality gate. "
                "Additional detail ensures the info field is clearly non-trivial and representative."
            ),
        }
    ])

    mock_result = MockCrawlResult(
        html=html,
        extracted_content=extracted_content,
        markdown=raw_markdown,
    )

    mocker.patch("src.internhunter.crawler.crawl.random.uniform", return_value=0)
    mocker.patch.object(Crawler, "_arun_with_retry", return_value=mock_result)

    crawler = Crawler()
    result = await crawler.extract_single_job(SimpleNamespace(), "https://example.com/job/normal")

    assert result is not None
    assert result.status == "pending"
    assert result.extraction_method == "css"
    assert result.title
    assert result.company
    assert result.location
    assert result.full_json_dump is not None
    assert result.raw_markdown == raw_markdown
    assert result.html == html
    assert result.screenshot is None


def test_topcv_section_helper_derives_description_and_requirements_from_exported_fixture():
    raw_html, raw_markdown = _load_exported_topcv_fixture("fb750e62")
    sections = _derive_topcv_section_fields(raw_markdown=raw_markdown, html_text=raw_html)

    assert sections["description"]
    assert sections["requirements"]


def test_topcv_section_helper_prefers_css_selected_container_text_over_raw_markdown():
    raw_markdown = (
        "Mô tả công việc\n"
        "Markdown description that should lose to the CSS-selected container.\n\n"
        "Yêu cầu ứng viên\n"
        "Markdown requirements that should lose to the CSS-selected container.\n\n"
        "Quyền lợi\n"
        "Markdown benefits that should lose to the CSS-selected container."
    )
    info_text = (
        "Mô tả công việc\n"
        "Container description from CSS-selected job content.\n\n"
        "Yêu cầu ứng viên\n"
        "Container requirements from CSS-selected job content.\n\n"
        "Quyền lợi\n"
        "Container benefits from CSS-selected job content."
    )

    sections = _derive_topcv_section_fields(raw_markdown=raw_markdown, info_text=info_text, html_text=None)

    assert sections["description"] == "Container description from CSS-selected job content."
    assert sections["requirements"] == "Container requirements from CSS-selected job content."
    assert sections["benefits"] == "Container benefits from CSS-selected job content."


def test_topcv_section_helper_reports_section_source_provenance():
    raw_markdown = (
        "M\u00f4 t\u1ea3 c\u00f4ng vi\u1ec7c\n"
        "Markdown description.\n\n"
        "Y\u00eau c\u1ea7u \u1ee9ng vi\u00ean\n"
        "Markdown requirements.\n\n"
        "Quy\u1ec1n l\u1ee3i\n"
        "Markdown benefits."
    )
    info_text = (
        "M\u00f4 t\u1ea3 c\u00f4ng vi\u1ec7c\n"
        "Container description.\n\n"
        "Y\u00eau c\u1ea7u \u1ee9ng vi\u00ean\n"
        "Container requirements.\n\n"
        "Quy\u1ec1n l\u1ee3i\n"
        "Container benefits."
    )

    sections, section_sources = _derive_topcv_section_fields_with_provenance(
        raw_markdown=raw_markdown,
        info_text=info_text,
        html_text=None,
    )

    assert sections["description"] == "Container description."
    assert sections["requirements"] == "Container requirements."
    assert sections["benefits"] == "Container benefits."
    assert section_sources["description"] in {"css_selected_job_content", "raw_markdown", "html_text"}
    assert section_sources["requirements"] in {"css_selected_job_content", "raw_markdown", "html_text"}
    assert section_sources["benefits"] in {"css_selected_job_content", "raw_markdown", "html_text"}


@pytest.mark.asyncio
async def test_extract_single_job_enriches_full_json_dump_with_description_requirements_benefits_work_location_and_working_time_from_topcv_fixture(mocker):
    raw_html, raw_markdown = _load_exported_topcv_fixture("fb750e62")
    extracted_content = json.dumps([
        {
            "title": "Software Engineer Test",
            "company": "Boundary Co",
            "salary": "Negotiable",
            "location": "Hanoi, Vietnam",
            "experience": "2 years",
            "info": (
                "This is a representative TopCV-like job detail page used for fixture-based extraction tests. "
                "It includes responsibilities, requirements, and benefits sections. "
                "The content is intentionally long enough to satisfy the crawler's CSS quality gate. "
                "Additional detail ensures the info field is clearly non-trivial and representative."
            ),
        }
    ])

    mock_result = MockCrawlResult(
        html=raw_html,
        extracted_content=extracted_content,
        markdown=raw_markdown,
    )

    mocker.patch("src.internhunter.crawler.crawl.random.uniform", return_value=0)
    mocker.patch.object(Crawler, "_arun_with_retry", return_value=mock_result)

    crawler = Crawler()
    result = await crawler.extract_single_job(SimpleNamespace(), "https://example.com/job/topcv-fixture")

    assert result is not None
    assert result.status == "pending"
    assert result.extraction_method == "css"
    assert result.full_json_dump["extraction_version"] == TOPCV_EXTRACTION_VERSION
    assert result.full_json_dump["description"]
    assert result.full_json_dump["requirements"]
    assert result.full_json_dump["benefits"]
    assert result.full_json_dump["work_location"]
    assert result.full_json_dump["working_time"]
    assert result.full_json_dump["section_sources"]["description"] in {"css_selected_job_content", "raw_markdown", "html_text"}
    assert result.full_json_dump["section_sources"]["requirements"] in {"css_selected_job_content", "raw_markdown", "html_text"}
    assert result.full_json_dump["section_sources"]["benefits"] in {"css_selected_job_content", "raw_markdown", "html_text"}
    assert result.full_json_dump["section_sources"]["work_location"] in {"css_selected_job_content", "raw_markdown", "html_text"}
    assert result.full_json_dump["section_sources"]["working_time"] in {"css_selected_job_content", "raw_markdown", "html_text"}
    assert result.full_json_dump["info"]


@pytest.mark.asyncio
async def test_extract_single_job_keeps_old_shallow_css_payload_compatible_when_sections_are_missing(mocker):
    html = (FIXTURE_DIR / "normal_job.html").read_text(encoding="utf-8")
    raw_markdown = "This is representative markdown for a TopCV job detail page without explicit section headings."
    extracted_content = json.dumps([
        {
            "title": "Software Engineer Test",
            "company": "Boundary Co",
            "salary": "Negotiable",
            "location": "Hanoi, Vietnam",
            "experience": "2 years",
            "info": (
                "This is a representative TopCV-like job detail page with only a shallow CSS payload. "
                "It intentionally contains a long block of plain text without explicit TopCV section headings, "
                "so the existing CSS quality gate still passes while the new section parser has nothing to extract. "
                "This keeps the regression test aligned with the current crawler behavior and preserves the fallback path."
            ),
        }
    ])

    mock_result = MockCrawlResult(
        html=html,
        extracted_content=extracted_content,
        markdown=raw_markdown,
    )

    mocker.patch("src.internhunter.crawler.crawl.random.uniform", return_value=0)
    mocker.patch.object(Crawler, "_arun_with_retry", return_value=mock_result)

    crawler = Crawler()
    result = await crawler.extract_single_job(SimpleNamespace(), "https://example.com/job/shallow-css")

    assert result is not None
    assert result.status == "pending"
    assert result.extraction_method == "css"
    assert result.full_json_dump["extraction_version"] == TOPCV_EXTRACTION_VERSION
    assert result.full_json_dump["info"].startswith("This is a representative TopCV-like job detail page with only a shallow CSS payload.")
    assert "description" not in result.full_json_dump or not result.full_json_dump["description"]
    assert "requirements" not in result.full_json_dump or not result.full_json_dump["requirements"]
    assert "benefits" not in result.full_json_dump or not result.full_json_dump["benefits"]
    assert "work_location" not in result.full_json_dump or not result.full_json_dump["work_location"]
    assert "working_time" not in result.full_json_dump or not result.full_json_dump["working_time"]
    assert result.full_json_dump["section_sources"]["description"] is None
    assert result.full_json_dump["section_sources"]["requirements"] is None
    assert result.full_json_dump["section_sources"]["benefits"] is None
    assert result.full_json_dump["section_sources"]["work_location"] is None
    assert result.full_json_dump["section_sources"]["working_time"] is None


@pytest.mark.asyncio
async def test_extract_single_job_marks_blocked_or_empty_content_as_blocked(mocker):
    html = (FIXTURE_DIR / "blocked_or_empty.html").read_text(encoding="utf-8")
    blocked_metadata = json.loads((FIXTURE_DIR / "blocked_or_empty.expected_failure.json").read_text(encoding="utf-8"))
    blocked_markdown = "Sorry, you have been blocked. Please enable cookies. Cloudflare Ray ID: 1234567890abcdef"

    mock_result = MockCrawlResult(
        html=html,
        extracted_content="[]",
        markdown=blocked_markdown,
    )

    mocker.patch("src.internhunter.crawler.crawl.random.uniform", return_value=0)
    mocker.patch.object(Crawler, "_arun_with_retry", return_value=mock_result)

    crawler = Crawler()
    result = await crawler.extract_single_job(SimpleNamespace(), "https://example.com/job/blocked")

    assert blocked_metadata["fixture_name"] == "blocked_or_empty"
    assert blocked_metadata["expected_valid"] is False
    assert blocked_metadata["expected_failure_reason"] == "blocked_or_empty_content"
    assert blocked_metadata["required_missing_fields"] == ["standardized_title", "description"]
    assert result is not None
    assert result.status == "blocked"
    assert result.extraction_method == "raw"
    assert result.raw_markdown is not None
    assert "Cloudflare Ray ID" in result.html
    assert result.full_json_dump["is_blocked"] is True
    assert result.full_json_dump["blocked_reason"] == "blocked_or_empty_content"


@pytest.mark.asyncio
async def test_extract_single_job_uses_raw_fallback_for_unparseable_css_content(mocker):
    html = (FIXTURE_DIR / "normal_job.html").read_text(encoding="utf-8")
    raw_markdown = "This is representative markdown for a TopCV job detail page with usable fallback text."

    mock_result = MockCrawlResult(
        html=html,
        extracted_content="[]",
        markdown=raw_markdown,
    )

    mocker.patch("src.internhunter.crawler.crawl.random.uniform", return_value=0)
    mocker.patch.object(Crawler, "_arun_with_retry", return_value=mock_result)

    crawler = Crawler()
    result = await crawler.extract_single_job(SimpleNamespace(), "https://example.com/job/raw-fallback")

    assert result is not None
    assert result.status == "pending"
    assert result.extraction_method == "raw"
    assert result.raw_markdown is not None
    assert result.raw_markdown == raw_markdown
    assert result.full_json_dump["is_blocked"] is False
    assert result.full_json_dump["blocked_reason"] == "empty_or_unparseable_css_content"


@pytest.mark.asyncio
async def test_fetch_job_links_stops_after_requested_limit(mocker):
    crawler = Crawler()
    crawler.search_urls = ["https://example.com/search"]
    crawler.max_pages = 10

    async def fake_fetch_single_page(crawler_obj, url, source_seed_url=None):
        page_num = 1
        if "page=" in url:
            page_num = int(url.split("page=")[-1])
        return (
            [
                {
                    "url": f"https://example.com/job/{page_num}",
                    "scraped_at": "2026-01-01T00:00:00Z",
                    "source": "topcv",
                    "source_seed_url": source_seed_url or "https://example.com/search",
                }
            ],
            None,
        )

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=set())
    mock_fetch = mocker.patch.object(Crawler, "_fetch_single_page", side_effect=fake_fetch_single_page)

    outcome = await crawler.fetch_job_links("run-limit-3", limit=3)

    assert outcome.is_success
    assert len(outcome.links) == 3
    assert all(link["source_seed_url"] == "https://example.com/search" for link in outcome.links)
    assert outcome.total_scraped == 6
    assert outcome.pages_scraped == 6
    assert mock_fetch.call_count == 6


@pytest.mark.asyncio
async def test_fetch_job_links_uses_per_run_session_id_for_fetch_config(mocker):
    crawler = Crawler()
    crawler.search_urls = ["https://example.com/search"]
    crawler.max_pages = 1
    captured = {}

    async def fake_arun_with_retry(crawler_obj, url, config, max_attempts=None):
        assert config.session_id == "topcv-run-fetch"
        return _make_fetch_result(
            success=True,
            error_message=None,
            html="<html><body>not blocked</body></html>",
            extracted_content=json.dumps([
                {"url": "https://example.com/job/1"}
            ]),
        )

    def fake_build_fetch_link_run_config(session_id=None):
        captured["session_id"] = session_id
        return SimpleNamespace(session_id=session_id)

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=set())
    mocker.patch("src.internhunter.crawler.crawl.build_fetch_link_run_config", side_effect=fake_build_fetch_link_run_config)
    mocker.patch.object(Crawler, "_arun_with_retry", side_effect=fake_arun_with_retry)

    outcome = await crawler.fetch_job_links("run-fetch", limit=1)

    assert captured["session_id"] == "topcv-run-fetch"
    assert outcome.is_success
    assert len(outcome.links) == 1
    assert outcome.links[0]["url"] == "https://example.com/job/1"


@pytest.mark.asyncio
async def test_fetch_job_links_tries_seeds_in_order_and_backfills_from_second_seed(mocker):
    crawler = Crawler()
    first_seed = "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"
    second_seed = "https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1"
    crawler.search_urls = [first_seed, second_seed]
    crawler.max_pages = 2

    async def fake_fetch_single_page(crawler_obj, url, source_seed_url=None):
        if url.startswith(first_seed):
            return [], FetchStatus.BLOCKED
        if url.startswith(second_seed):
            page_num = 1 if "page=" not in url else int(url.split("page=")[-1])
            return (
                [
                    {
                        "url": f"https://example.com/job/seed-2-{page_num}",
                        "scraped_at": "2026-01-01T00:00:00Z",
                        "source": "topcv",
                        "source_seed_url": source_seed_url or second_seed,
                    }
                ],
                None,
            )
        raise AssertionError(f"unexpected url: {url}")

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=set())
    mock_fetch = mocker.patch.object(Crawler, "_fetch_single_page", side_effect=fake_fetch_single_page)

    outcome = await crawler.fetch_job_links("run-seed-fallback", limit=2)

    assert outcome.is_success
    assert len(outcome.links) == 2
    assert all(link["source_seed_url"] == second_seed for link in outcome.links)
    assert outcome.total_scraped == 2
    assert outcome.pages_scraped == 2
    assert mock_fetch.call_count == 3


@pytest.mark.asyncio
async def test_fetch_job_links_force_recrawl_skips_dedup_filtering(mocker):
    crawler = Crawler()
    crawler.search_urls = ["https://example.com/search"]
    crawler.max_pages = 10

    async def fake_fetch_single_page(crawler_obj, url, source_seed_url=None):
        page_num = 1
        if "page=" in url:
            page_num = int(url.split("page=")[-1])
        return (
            [
                {
                    "url": f"https://example.com/job/{page_num}",
                    "scraped_at": "2026-01-01T00:00:00Z",
                    "source": "topcv",
                    "source_seed_url": source_seed_url or "https://example.com/search",
                }
            ],
            None,
        )

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch.object(Crawler, "_fetch_single_page", side_effect=fake_fetch_single_page)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=AssertionError("dedup should be bypassed in force-recrawl mode"))
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=set())

    outcome = await crawler.fetch_job_links("run-force-recrawl", limit=3, force_recrawl=True)

    assert outcome.is_success
    assert len(outcome.links) == 3
    assert outcome.total_scraped == 6
    assert outcome.pages_scraped == 6


@pytest.mark.asyncio
async def test_crawl_jobs_force_recrawl_skips_defensive_dedup_recheck(mocker):
    crawler = Crawler()
    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=0)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=AssertionError("dedup should be bypassed in force-recrawl mode"))
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.save_raw_job", return_value=True)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.save_to_audit", return_value=True)
    mocker.patch.object(Crawler, "extract_single_job", return_value=DummyExtraction("https://example.com/job/force"))

    saved, failed = await crawler.crawl_jobs([{"url": "https://example.com/job/force"}], "run-force-recrawl", force_recrawl=True)

    assert saved == 1
    assert failed == 0


@pytest.mark.asyncio
async def test_crawl_jobs_uses_per_run_session_id_for_detail_config(mocker):
    crawler = Crawler()
    captured = {}

    async def fake_arun_with_retry(crawler_obj, url, config, max_attempts=None):
        assert config.session_id == "topcv-run-detail"
        return MockCrawlResult(
            html=(
                "<html><body>"
                "<h1 class='job-detail-title'>TopCV Job</h1>"
                "<div class='job-detail__info--section-content-value'>Company</div>"
                "<div class='job-description'>"
                "This is a representative TopCV-like job detail page used for fixture-based extraction tests. "
                "It includes responsibilities, requirements, and benefits sections. "
                "The content is intentionally long enough to satisfy the crawler's CSS quality gate. "
                "Additional detail ensures the info field is clearly non-trivial and representative."
                "</div>"
                "</body></html>"
            ),
            extracted_content=json.dumps([
                {
                    "title": "Software Engineer Test",
                    "company": "Boundary Co",
                    "salary": "Negotiable",
                    "location": "Hanoi, Vietnam",
                    "experience": "2 years",
                    "info": (
                        "This is a representative TopCV-like job detail page used for fixture-based extraction tests. "
                        "It includes responsibilities, requirements, and benefits sections. "
                        "The content is intentionally long enough to satisfy the crawler's CSS quality gate. "
                        "Additional detail ensures the info field is clearly non-trivial and representative."
                    ),
                }
            ]),
            markdown="This is representative markdown for a TopCV job detail page.",
        )

    def fake_build_extract_detail_run_config(session_id=None):
        captured["session_id"] = session_id
        return SimpleNamespace(session_id=session_id)

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=0)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=set())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.save_raw_job", return_value=True)
    mocker.patch("src.internhunter.crawler.crawl.random.uniform", return_value=0)
    mocker.patch("src.internhunter.crawler.crawl.build_extract_detail_run_config", side_effect=fake_build_extract_detail_run_config)
    mocker.patch.object(Crawler, "_arun_with_retry", side_effect=fake_arun_with_retry)

    saved, failed = await crawler.crawl_jobs(
        [{"url": "https://example.com/job/detail"}],
        "run-detail",
        force_recrawl=True,
    )

    assert captured["session_id"] == "topcv-run-detail"
    assert saved == 1
    assert failed == 0


@pytest.mark.asyncio
async def test_crawl_jobs_persists_successful_css_artifacts_to_raw_job(mocker, test_db_session):
    from src.internhunter.storage.models import RawJobDB

    crawler = Crawler()
    saved_payload = {}

    async def fake_arun_with_retry(crawler_obj, url, config, max_attempts=None):
        return MockCrawlResult(
            html=(
                "<html><body>"
                "<h1 class='job-detail-title'>TopCV Job</h1>"
                "<div class='job-detail__info--section-content-value'>Company</div>"
                "<div class='job-description'>"
                "This is a representative TopCV-like job detail page used for fixture-based extraction tests. "
                "It includes responsibilities, requirements, and benefits sections. "
                "The content is intentionally long enough to satisfy the crawler's CSS quality gate. "
                "Additional detail ensures the info field is clearly non-trivial and representative."
                "</div>"
                "</body></html>"
            ),
            extracted_content=json.dumps([
                {
                    "title": "Software Engineer Test",
                    "company": "Boundary Co",
                    "salary": "Negotiable",
                    "location": "Hanoi, Vietnam",
                    "experience": "2 years",
                    "info": (
                        "This is a representative TopCV-like job detail page used for fixture-based extraction tests. "
                        "It includes responsibilities, requirements, and benefits sections. "
                        "The content is intentionally long enough to satisfy the crawler's CSS quality gate. "
                        "Additional detail ensures the info field is clearly non-trivial and representative."
                    ),
                }
            ]),
            markdown="This is representative markdown for a TopCV job detail page.",
        )

    def fake_save_raw_job(job_data):
        saved_payload.update(job_data)
        row = RawJobDB(
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
        )
        test_db_session.add(row)
        test_db_session.commit()
        return True

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=0)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=set())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.save_raw_job", side_effect=fake_save_raw_job)
    mocker.patch("src.internhunter.crawler.crawl.random.uniform", return_value=0)
    mocker.patch.object(Crawler, "_arun_with_retry", side_effect=fake_arun_with_retry)
    mocker.patch.object(Crawler, "_save_screenshot", return_value="C:/tmp/crawl-screenshot.png")

    saved, failed = await crawler.crawl_jobs(
        [{"url": "https://example.com/job/detail", "source_seed_url": "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"}],
        "run-artifacts",
        force_recrawl=True,
    )

    assert saved == 1
    assert failed == 0
    assert saved_payload["html_content"].startswith("<html><body>")
    assert saved_payload["raw_markdown"] == "This is representative markdown for a TopCV job detail page."
    assert saved_payload["screenshot_path"] == "C:/tmp/crawl-screenshot.png"
    saved_job = test_db_session.query(RawJobDB).filter_by(url="https://example.com/job/detail").first()
    assert saved_job is not None
    assert saved_job.html_content.startswith("<html><body>")
    assert saved_job.raw_markdown == "This is representative markdown for a TopCV job detail page."
    assert saved_job.screenshot_path == "C:/tmp/crawl-screenshot.png"


@pytest.mark.asyncio
async def test_crawl_jobs_applies_detail_crawl_delay_before_each_attempt(mocker):
    crawler = Crawler()
    events = []

    async def fake_apply_detail_crawl_delay():
        events.append("delay")

    async def fake_extract_single_job(crawler_obj, url):
        events.append(f"extract:{url}")
        return DummyExtraction(url)

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=0)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=set())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.save_raw_job", return_value=True)
    mocker.patch.object(Crawler, "_apply_detail_crawl_delay", side_effect=fake_apply_detail_crawl_delay)
    mocker.patch.object(Crawler, "extract_single_job", side_effect=fake_extract_single_job)

    saved, failed = await crawler.crawl_jobs(
        [{"url": "https://example.com/job/1"}, {"url": "https://example.com/job/2"}],
        "run-delay",
        force_recrawl=True,
    )

    assert saved == 2
    assert failed == 0
    assert events == [
        "delay",
        "extract:https://example.com/job/1",
        "delay",
        "extract:https://example.com/job/2",
    ]


@pytest.mark.asyncio
async def test_crawl_jobs_stops_after_two_blocked_detail_pages(mocker):
    crawler = Crawler()
    crawler.blocked_early_stop_threshold = 2
    urls = [
        "https://example.com/job/blocked-1",
        "https://example.com/job/blocked-2",
        "https://example.com/job/allowed-3",
    ]
    events = []

    async def fake_apply_detail_crawl_delay():
        events.append("delay")

    async def fake_extract_single_job(crawler_obj, url):
        events.append(f"extract:{url}")
        if "allowed-3" in url:
            raise AssertionError("crawl should have stopped before the third blocked page")
        extraction = DummyExtraction(url)
        extraction.status = "blocked"
        extraction.html = (
            "<html><body>"
            "Please enable cookies. Sorry, you have been blocked. "
            "You are unable to access topcv.vn. Cloudflare Ray ID: abc123. "
            "Performance &amp; security by Cloudflare."
            "</body></html>"
        )
        extraction.raw_markdown = "Sorry, you have been blocked"
        return extraction

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=0)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=set())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.save_raw_job", return_value=True)
    mocker.patch.object(Crawler, "_apply_detail_crawl_delay", side_effect=fake_apply_detail_crawl_delay)
    mocker.patch.object(Crawler, "extract_single_job", side_effect=fake_extract_single_job)

    saved, failed = await crawler.crawl_jobs([{ "url": url } for url in urls], "run-stop-early", force_recrawl=True)

    assert saved == 2
    assert failed == 0
    assert crawler._blocked_detail_count_in_run == 0
    assert events == [
        "delay",
        f"extract:{urls[0]}",
        "delay",
        f"extract:{urls[1]}",
    ]


@pytest.mark.asyncio
async def test_crawl_jobs_skips_recently_blocked_urls_even_in_force_recrawl_mode(mocker, test_db_session):
    from src.internhunter.storage.models import AuditJobDB

    crawler = Crawler()
    blocked_url = "https://example.com/job/recent-blocked"
    allowed_url = "https://example.com/job/allowed"
    blocked_seed_url = "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=0)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=AssertionError("dedup should be bypassed in force-recrawl mode"))
    mocker.patch(
        "src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls",
        return_value={blocked_url},
    )
    save_raw_job_mock = mocker.patch("src.internhunter.crawler.crawl.ETLRepository.save_raw_job", return_value=True)

    async def fake_extract_single_job(crawler_obj, url):
        assert url == allowed_url
        return DummyExtraction(url)

    extract_mock = mocker.patch.object(Crawler, "extract_single_job", side_effect=fake_extract_single_job)

    saved, failed = await crawler.crawl_jobs(
        [{"url": blocked_url, "source_seed_url": blocked_seed_url}, {"url": allowed_url, "source_seed_url": blocked_seed_url}],
        "run-blocked-cooldown",
        force_recrawl=True,
    )

    assert saved == 1
    assert failed == 0
    assert extract_mock.call_count == 1
    save_raw_job_mock.assert_called_once()

    audit_row = test_db_session.query(AuditJobDB).filter_by(url=blocked_url).first()
    assert audit_row is not None
    assert audit_row.error_type == "CRAWL_SKIPPED"
    assert audit_row.error_message == "recently_blocked_cooldown"
    assert audit_row.crawl_run_id == "run-blocked-cooldown"
    assert audit_row.source_seed_url == blocked_seed_url


@pytest.mark.asyncio
async def test_crawl_jobs_crawls_non_blocked_url_normally_when_no_recent_blocked_cooldown(mocker):
    crawler = Crawler()
    allowed_url = "https://example.com/job/allowed-normal"
    seed_url = "https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1"

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=0)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=AssertionError("dedup should be bypassed in force-recrawl mode"))
    mocker.patch(
        "src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls",
        return_value=set(),
    )
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.save_raw_job", return_value=True)

    async def fake_extract_single_job(crawler_obj, url):
        assert url == allowed_url
        return DummyExtraction(url)

    extract_mock = mocker.patch.object(Crawler, "extract_single_job", side_effect=fake_extract_single_job)

    saved, failed = await crawler.crawl_jobs(
        [{"url": allowed_url, "source_seed_url": seed_url}],
        "run-no-blocked-cooldown",
        force_recrawl=True,
    )

    assert saved == 1
    assert failed == 0
    assert extract_mock.call_count == 1


@pytest.mark.asyncio
async def test_fetch_job_links_returns_replacement_eligible_links_when_recently_blocked_candidates_are_filtered(mocker):
    crawler = Crawler()
    crawler.search_urls = ["https://example.com/search"]
    crawler.max_pages = 10
    blocked_urls = {
        "https://example.com/job/1",
        "https://example.com/job/2",
    }

    async def fake_fetch_single_page(crawler_obj, url, source_seed_url=None):
        page_num = 1
        if "page=" in url:
            page_num = int(url.split("page=")[-1])
        return (
            [
                {
                    "url": f"https://example.com/job/{page_num}",
                    "scraped_at": "2026-01-01T00:00:00Z",
                    "source": "topcv",
                    "source_seed_url": source_seed_url or "https://example.com/search",
                }
            ],
            None,
        )

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=blocked_urls)
    mock_fetch = mocker.patch.object(Crawler, "_fetch_single_page", side_effect=fake_fetch_single_page)

    outcome = await crawler.fetch_job_links("run-replacement", limit=3)

    assert outcome.is_success
    assert len(outcome.links) == 3
    assert [link["url"] for link in outcome.links] == [
        "https://example.com/job/3",
        "https://example.com/job/4",
        "https://example.com/job/5",
    ]
    assert all(link["source_seed_url"] == "https://example.com/search" for link in outcome.links)
    assert outcome.total_scraped == 6
    assert outcome.pages_scraped == 6
    assert mock_fetch.call_count == 6


@pytest.mark.asyncio
async def test_fetch_job_links_force_recrawl_bypasses_dedup_but_filters_recently_blocked_urls(mocker):
    crawler = Crawler()
    crawler.search_urls = ["https://example.com/search"]
    crawler.max_pages = 10
    blocked_urls = {
        "https://example.com/job/1",
        "https://example.com/job/2",
    }

    async def fake_fetch_single_page(crawler_obj, url, source_seed_url=None):
        page_num = 1
        if "page=" in url:
            page_num = int(url.split("page=")[-1])
        return (
            [
                {
                    "url": f"https://example.com/job/{page_num}",
                    "scraped_at": "2026-01-01T00:00:00Z",
                    "source": "topcv",
                    "source_seed_url": source_seed_url or "https://example.com/search",
                }
            ],
            None,
        )

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch.object(Crawler, "_fetch_single_page", side_effect=fake_fetch_single_page)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=AssertionError("dedup should be bypassed in force-recrawl mode"))
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=blocked_urls)

    outcome = await crawler.fetch_job_links("run-force-recrawl-blocked", limit=3, force_recrawl=True)

    assert outcome.is_success
    assert len(outcome.links) == 3
    assert [link["url"] for link in outcome.links] == [
        "https://example.com/job/3",
        "https://example.com/job/4",
        "https://example.com/job/5",
    ]
    assert all(link["source_seed_url"] == "https://example.com/search" for link in outcome.links)
    assert outcome.total_scraped == 6
    assert outcome.pages_scraped == 6


@pytest.mark.asyncio
async def test_fetch_job_links_returns_no_new_when_all_candidates_recently_blocked(mocker):
    crawler = Crawler()
    crawler.search_urls = ["https://example.com/search"]
    crawler.max_pages = 3

    blocked_urls = {
        "https://example.com/job/1",
        "https://example.com/job/2",
        "https://example.com/job/3",
    }

    async def fake_fetch_single_page(crawler_obj, url, source_seed_url=None):
        page_num = 1
        if "page=" in url:
            page_num = int(url.split("page=")[-1])
        return (
            [
                {
                    "url": f"https://example.com/job/{page_num}",
                    "scraped_at": "2026-01-01T00:00:00Z",
                    "source": "topcv",
                    "source_seed_url": source_seed_url or "https://example.com/search",
                }
            ],
            None,
        )

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_recently_blocked_urls", return_value=blocked_urls)
    mocker.patch.object(Crawler, "_fetch_single_page", side_effect=fake_fetch_single_page)

    outcome = await crawler.fetch_job_links("run-all-blocked", limit=3)

    assert outcome.status == FetchStatus.NO_NEW
    assert outcome.links == []
    assert outcome.total_scraped == 3
    assert outcome.pages_scraped == 3


@pytest.mark.asyncio
async def test_crawl_jobs_force_recrawl_refreshes_duplicate_raw_job_without_collision(mocker, test_db_session):
    from src.internhunter.storage.models import RawJobDB
    from src.internhunter.storage.repositories.etl import ETLRepository

    crawler = Crawler()
    repo = ETLRepository()
    existing_url = "https://example.com/job/force-refresh"
    assert repo.save_raw_job(
        {
            "url": existing_url,
            "title": "Original Title",
            "company": "Original Co",
            "location": "Remote",
            "full_json_dump": {"version": 1},
            "status": "pending",
            "extraction_method": "css",
            "raw_markdown": "original markdown",
        }
    )

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=1)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=AssertionError("dedup should be bypassed in force-recrawl mode"))
    mocker.patch.object(Crawler, "extract_single_job", return_value=DummyExtraction(existing_url))

    saved, failed = await crawler.crawl_jobs([{"url": existing_url}], "run-force-recrawl", force_recrawl=True)

    assert saved == 1
    assert failed == 0

    saved_job = test_db_session.query(RawJobDB).filter_by(url=existing_url).first()
    assert saved_job is not None
    assert saved_job.retry_count == 1
    assert saved_job.title == "Title"
    assert saved_job.crawl_run_id == "run-force-recrawl"


@pytest.mark.asyncio
async def test_crawl_jobs_saves_blocked_jobs_as_blocked_not_pending(mocker, test_db_session):
    from src.internhunter.storage.models import RawJobDB, AuditJobDB

    crawler = Crawler()
    blocked_url = "https://example.com/job/cloudflare-blocked"
    blocked_seed_url = "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"
    blocked_extraction = DummyExtraction(blocked_url)
    blocked_extraction.status = "blocked"
    blocked_extraction.html = (
        "<html><body>"
        "Please enable cookies. Sorry, you have been blocked. "
        "You are unable to access topcv.vn. Cloudflare Ray ID: abc123. "
        "Performance &amp; security by Cloudflare."
        "</body></html>"
    )

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=0)
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.filter_new_links", side_effect=lambda links: links)
    mocker.patch("src.internhunter.crawler.crawl.Crawler.extract_single_job", return_value=blocked_extraction)

    saved, failed = await crawler.crawl_jobs(
        [{"url": blocked_url, "source_seed_url": blocked_seed_url}],
        "run-blocked-case",
        force_recrawl=True,
    )

    assert saved == 1
    assert failed == 0

    saved_job = test_db_session.query(RawJobDB).filter_by(url=blocked_url).first()
    assert saved_job is not None
    assert saved_job.status == "blocked"
    assert saved_job.crawl_run_id == "run-blocked-case"
    assert saved_job.source_seed_url == blocked_seed_url

    audit_row = test_db_session.query(AuditJobDB).filter_by(url=blocked_url).first()
    assert audit_row is not None
    assert audit_row.error_type == "BOT_DETECTED"
    assert audit_row.error_message == "blocked_or_empty_content"
    assert audit_row.crawl_run_id == "run-blocked-case"
    assert audit_row.source_seed_url == blocked_seed_url


def test_classify_fetch_error_groups_common_failures():
    assert _classify_fetch_error("Timed out waiting for browser response") == "crawl_timeout"
    assert _classify_fetch_error("Browser page crashed unexpectedly") == "browser_error"
    assert _classify_fetch_error("Network connection reset while loading page") == "network_error"
    assert _classify_fetch_error("Navigation failed after page.goto timeout") == "navigation_error"
    assert _classify_fetch_error("JSON parse error while reading extracted_content") == "parse_error"
    assert _classify_fetch_error("Empty extraction after retries") == "empty_extraction"
    assert _classify_fetch_error("Sorry, you have been blocked") == "blocked_or_empty_content"
    assert _classify_fetch_error(None) == "unknown_crawl_error"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_message", "expected_reason", "expected_status"),
    [
        ("Timed out waiting for browser response", "crawl_timeout", FetchStatus.NETWORK_FAIL),
        ("Navigation failed after page.goto timeout", "navigation_error", FetchStatus.NETWORK_FAIL),
        ("Browser page crashed unexpectedly", "browser_error", FetchStatus.NETWORK_FAIL),
    ],
)
async def test_fetch_single_page_preserves_classified_failure_reason(mocker, error_message, expected_reason, expected_status):
    crawler = Crawler()
    mock_result = _make_fetch_result(
        success=False,
        error_message=error_message,
        html="<html><body>Unrelated page body</body></html>",
    )

    mocker.patch.object(Crawler, "_arun_with_retry", return_value=mock_result)

    links, status = await crawler._fetch_single_page(SimpleNamespace(), "https://example.com/search")

    assert links == []
    assert status == expected_status
    assert crawler._last_fetch_failure_reason == expected_reason
    assert crawler._last_fetch_failure_message == error_message


@pytest.mark.asyncio
async def test_fetch_single_page_classifies_blocked_html_before_generic_failure(mocker):
    crawler = Crawler()
    blocked_html = (FIXTURE_DIR / "blocked_or_empty.html").read_text(encoding="utf-8")
    mock_result = _make_fetch_result(
        success=False,
        error_message="Some generic crawl4ai failure",
        html=blocked_html,
    )

    mocker.patch.object(Crawler, "_arun_with_retry", return_value=mock_result)

    links, status = await crawler._fetch_single_page(SimpleNamespace(), "https://example.com/blocked")

    assert links == []
    assert status == FetchStatus.BLOCKED
    assert crawler._last_fetch_failure_reason == "blocked_or_empty_content"
    assert crawler._last_fetch_failure_message == "Some generic crawl4ai failure"


@pytest.mark.asyncio
async def test_fetch_job_links_includes_preserved_fetch_failure_reason_in_outcome_error(mocker):
    crawler = Crawler()
    crawler.search_urls = ["https://example.com/search"]
    crawler.max_pages = 1

    async def fake_fetch_single_page(crawler_obj, url, source_seed_url=None):
        crawler._last_fetch_failure_reason = "crawl_timeout"
        crawler._last_fetch_failure_message = "Timed out waiting for browser response"
        return [], FetchStatus.NETWORK_FAIL

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch.object(Crawler, "_fetch_single_page", side_effect=fake_fetch_single_page)

    outcome = await crawler.fetch_job_links("run-fail", limit=1)

    assert outcome.status == FetchStatus.NETWORK_FAIL
    assert outcome.error == "crawl_timeout: Timed out waiting for browser response"


@pytest.mark.asyncio
async def test_crawl_jobs_records_classified_crawl_failure_reason(mocker, test_db_session):
    from src.internhunter.storage.models import AuditJobDB

    crawler = Crawler()
    failure_url = "https://example.com/job/timeout-failure"
    failure_seed_url = "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"

    async def fake_extract_single_job(crawler_handle, url):
        crawler._last_extract_failure_reason = "crawl_timeout"
        crawler._last_extract_failure_message = "Timed out waiting for browser response"
        return None

    mocker.patch("src.internhunter.crawler.crawl.AsyncWebCrawler", return_value=DummyAsyncWebCrawler())
    mocker.patch("src.internhunter.crawler.crawl.ETLRepository.get_raw_jobs_count", return_value=0)
    mocker.patch.object(Crawler, "extract_single_job", side_effect=fake_extract_single_job)

    saved, failed = await crawler.crawl_jobs(
        [{"url": failure_url, "source_seed_url": failure_seed_url}],
        "run-timeout-case",
        force_recrawl=True,
    )

    assert saved == 0
    assert failed == 1

    audit_row = test_db_session.query(AuditJobDB).filter_by(url=failure_url).first()
    assert audit_row is not None
    assert audit_row.error_type == "CRAWL_FAILED"
    assert audit_row.error_message == "crawl_timeout"
    assert audit_row.crawl_run_id == "run-timeout-case"
    assert audit_row.source_seed_url == failure_seed_url

