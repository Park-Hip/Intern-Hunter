from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src.internhunter.storage.models import AuditJobDB, RawJobDB
from src.scripts.export_crawl_fixtures import export_crawl_fixtures


def _make_raw_job(**overrides):
    payload = {
        "url": "https://www.topcv.vn/viec-lam/12345-example-job.html",
        "crawl_run_id": "run-export",
        "source_seed_url": "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
        "title": "Example Job",
        "company": "Example Co",
        "location": "Hanoi",
        "full_json_dump": {"title": "Example Job", "info": "A" * 250},
        "status": "pending",
        "extraction_method": "css",
        "raw_markdown": "markdown body",
        "html_content": "<html><body>example job</body></html>",
        "screenshot_path": None,
        "created_at": datetime.now(timezone.utc) - timedelta(days=1),
        "updated_at": datetime.now(timezone.utc),
        "last_crawled_at": datetime.now(timezone.utc),
    }
    payload.update(overrides)
    return RawJobDB(**payload)


def test_export_crawl_fixtures_writes_metadata_json_for_successful_css_job(test_db_session, tmp_path):
    raw_css = _make_raw_job(url="https://www.topcv.vn/viec-lam/12345-css-job.html", title="CSS Job")
    raw_raw = _make_raw_job(
        url="https://www.topcv.vn/viec-lam/12346-raw-job.html",
        title="RAW Job",
        extraction_method="raw",
    )
    test_db_session.add_all([raw_css, raw_raw])
    test_db_session.commit()

    summary = export_crawl_fixtures(
        session=test_db_session,
        crawl_run_id="run-export",
        output_root=tmp_path / "crawl_samples" / "topcv",
    )

    assert summary["exported_count"] == 2
    assert summary["urls"][0] == raw_css.url
    assert summary["urls"][1] == raw_raw.url
    export_dir = tmp_path / "crawl_samples" / "topcv" / "run-export"
    css_dir = next(p for p in export_dir.iterdir() if p.is_dir() and p.name.startswith(f"{raw_css.id:06d}"))
    metadata = json.loads((css_dir / "metadata.json").read_text(encoding="utf-8"))

    assert metadata["raw_job_id"] == raw_css.id
    assert metadata["crawl_run_id"] == "run-export"
    assert metadata["source_seed_url"].endswith("ai-engineer?sba=1")
    assert metadata["title"] == "CSS Job"
    assert metadata["company"] == "Example Co"
    assert metadata["html_path"] == "raw.html"
    assert metadata["raw_markdown_path"] == "raw_markdown.txt"
    assert metadata["full_json_dump_path"] == "full_json_dump.json"
    assert metadata["screenshot_path"] is None
    assert metadata["missing_fields"] == ["screenshot"]
    assert (css_dir / "raw.html").read_text(encoding="utf-8") == "<html><body>example job</body></html>"
    assert (css_dir / "raw_markdown.txt").read_text(encoding="utf-8") == "markdown body"


def test_export_crawl_fixtures_exports_markdown_and_full_json_dump_when_present(test_db_session, tmp_path):
    screenshot_src = tmp_path / "shot.png"
    screenshot_src.write_bytes(b"fake-png")
    raw_job = _make_raw_job(
        raw_markdown="markdown body here",
        full_json_dump={"foo": "bar"},
        screenshot_path=str(screenshot_src),
    )
    test_db_session.add(raw_job)
    test_db_session.commit()

    summary = export_crawl_fixtures(
        session=test_db_session,
        crawl_run_id="run-export",
        output_root=tmp_path / "crawl_samples" / "topcv",
        limit=1,
    )

    assert summary["exported_count"] == 1
    job_dir = next(p for p in (tmp_path / "crawl_samples" / "topcv" / "run-export").iterdir() if p.is_dir())
    assert (job_dir / "raw_markdown.txt").read_text(encoding="utf-8") == "markdown body here"
    assert json.loads((job_dir / "full_json_dump.json").read_text(encoding="utf-8")) == {"foo": "bar"}
    assert (job_dir / "shot.png").read_bytes() == b"fake-png"


def test_export_crawl_fixtures_handles_missing_html_and_screenshot_without_crashing(test_db_session, tmp_path):
    raw_job = _make_raw_job(html_content=None, screenshot_path=None)
    test_db_session.add(raw_job)
    test_db_session.commit()

    summary = export_crawl_fixtures(
        session=test_db_session,
        crawl_run_id="run-export",
        output_root=tmp_path / "crawl_samples" / "topcv",
    )

    assert summary["exported_count"] == 1
    job_dir = next(p for p in (tmp_path / "crawl_samples" / "topcv" / "run-export").iterdir() if p.is_dir())
    metadata = json.loads((job_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["html_path"] is None
    assert metadata["screenshot_path"] is None
    assert "html" in metadata["missing_fields"]
    assert "screenshot" in metadata["missing_fields"]


def test_export_crawl_fixtures_filters_by_crawl_run_id_and_limit(test_db_session, tmp_path):
    test_db_session.add_all(
        [
            _make_raw_job(
                url="https://www.topcv.vn/viec-lam/10001-ai-job.html",
                crawl_run_id="run-a",
                title="AI Job",
            ),
            _make_raw_job(
                url="https://www.topcv.vn/viec-lam/10002-ds-job.html",
                crawl_run_id="run-b",
                title="DS Job",
            ),
        ]
    )
    test_db_session.commit()

    summary = export_crawl_fixtures(
        session=test_db_session,
        crawl_run_id="run-a",
        output_root=tmp_path / "crawl_samples" / "topcv",
        limit=1,
    )

    assert summary["exported_count"] == 1
    assert summary["urls"] == ["https://www.topcv.vn/viec-lam/10001-ai-job.html"]
    run_a_dir = tmp_path / "crawl_samples" / "topcv" / "run-a"
    assert run_a_dir.exists()
    assert not (tmp_path / "crawl_samples" / "topcv" / "run-b").exists()


def test_export_crawl_fixtures_can_export_blocked_rows_when_requested(test_db_session, tmp_path):
    screenshot_src = tmp_path / "blocked-screenshot.png"
    screenshot_src.write_bytes(b"fake-png")

    blocked_raw = _make_raw_job(
        url="https://www.topcv.vn/viec-lam/99999-blocked.html",
        crawl_run_id="run-blocked",
        status="blocked",
        extraction_method="raw",
        raw_markdown=None,
        html_content=None,
        screenshot_path=None,
    )
    test_db_session.add(blocked_raw)
    test_db_session.flush()
    test_db_session.add(
        AuditJobDB(
            url=blocked_raw.url,
            crawl_run_id="run-blocked",
            source_seed_url=blocked_raw.source_seed_url,
            error_type="BOT_DETECTED",
            error_message="blocked_or_empty_content",
            html_content="<html><body>blocked</body></html>",
            screenshot_path=str(screenshot_src),
            created_at=datetime.now(timezone.utc),
        )
    )
    test_db_session.commit()

    summary = export_crawl_fixtures(
        session=test_db_session,
        crawl_run_id="run-blocked",
        output_root=tmp_path / "crawl_samples" / "topcv",
        statuses=["blocked"],
    )

    assert summary["exported_count"] == 1
    job_dir = next(p for p in (tmp_path / "crawl_samples" / "topcv" / "run-blocked").iterdir() if p.is_dir())
    assert (job_dir / "raw.html").read_text(encoding="utf-8") == "<html><body>blocked</body></html>"
    assert any(path.name.startswith("blocked-screenshot") for path in job_dir.iterdir())
