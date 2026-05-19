from datetime import datetime, timedelta, timezone

from src.internhunter.storage.models import AuditJobDB, CleanJobDB, RawJobDB
from src.scripts.crawl_quality_report import build_crawl_quality_report, format_crawl_quality_report


def test_build_crawl_quality_report_counts_and_filters(test_db_session):
    raw_css = RawJobDB(
        url="https://example.com/job/css",
        crawl_run_id="run-a",
        source_seed_url="https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
        title="Data Scientist",
        company="TopCV",
        location="Hanoi",
        full_json_dump={
            "title": "Data Scientist",
            "info": "A" * 250,
            "description": "Description block",
            "requirements": "Requirements block",
            "benefits": "Benefits block",
            "work_location": "Hanoi",
            "working_time": "Full-time",
            "extraction_version": "topcv_section_v2",
            "section_sources": {
                "description": "css_selected_job_content",
                "requirements": "css_selected_job_content",
                "benefits": "css_selected_job_content",
                "work_location": "css_selected_job_content",
                "working_time": "css_selected_job_content",
            },
        },
        status="pending",
        extraction_method="css",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        updated_at=datetime.now(timezone.utc) - timedelta(hours=1),
        last_crawled_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    raw_raw = RawJobDB(
        url="https://example.com/job/raw",
        crawl_run_id="run-a",
        source_seed_url="https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
        title="Unknown (RAW)",
        company="Unknown (RAW)",
        location="Unknown",
        full_json_dump={"error": "CSS extraction failed", "is_blocked": False, "blocked_reason": None},
        status="pending",
        extraction_method="raw",
        raw_markdown="raw markdown " * 20,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        last_crawled_at=datetime.now(timezone.utc) - timedelta(minutes=30),
    )
    blocked_raw = RawJobDB(
        url="https://example.com/job/blocked",
        crawl_run_id="run-b",
        source_seed_url="https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
        title="Unknown (RAW)",
        company="Unknown (RAW)",
        location="Unknown",
        full_json_dump={"error": "CSS extraction failed", "is_blocked": True, "blocked_reason": "blocked_or_empty_content"},
        status="blocked",
        extraction_method="raw",
        raw_markdown="blocked markdown",
        created_at=datetime.now(timezone.utc) - timedelta(hours=3),
        updated_at=datetime.now(timezone.utc) - timedelta(hours=3),
        last_crawled_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    test_db_session.add_all([raw_css, raw_raw, blocked_raw])
    test_db_session.commit()

    clean = CleanJobDB(
        raw_job_id=raw_css.id,
        standardized_title="Data Scientist",
        job_level="Mid",
        is_internship=False,
        cities=["Hanoi"],
        tech_stack=["Python"],
        technical_competencies=[],
        domain_knowledge=["Machine Learning"],
    )
    blocked_clean = CleanJobDB(
        raw_job_id=blocked_raw.id,
        standardized_title="Machine Learning Engineer",
        job_level="Senior",
        is_internship=False,
        cities=["Ho Chi Minh City"],
        tech_stack=["Python"],
        technical_competencies=[],
        domain_knowledge=["MLOps"],
    )
    test_db_session.add_all([clean, blocked_clean])
    test_db_session.add_all(
        [
            AuditJobDB(
                url="https://example.com/job/blocked",
                crawl_run_id="run-a",
                source_seed_url="https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
                error_type="BOT_DETECTED",
                error_message="blocked_or_empty_content",
            ),
            AuditJobDB(
                url="https://example.com/job/raw",
                crawl_run_id="run-a",
                source_seed_url="https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
                error_type="CRAWL_FAILED",
                error_message="crawl_timeout",
            ),
            AuditJobDB(
                url="https://example.com/job/global-noise",
                error_type="CRAWL_FAILED",
                error_message="browser_error",
            ),
            AuditJobDB(
                url="https://example.com/job/skipped",
                crawl_run_id="run-a",
                source_seed_url="https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
                error_type="CRAWL_SKIPPED",
                error_message="recently_blocked_cooldown",
            ),
        ]
    )
    test_db_session.commit()

    report = build_crawl_quality_report(test_db_session, crawl_run_id="run-a", recent_limit=5)

    assert report["crawl_run_id"] == "run-a"
    assert report["total_raw_jobs"] == 2
    assert report["css_success_count"] == 1
    assert report["raw_fallback_pending_count"] == 1
    assert report["current_usable_raw_count"] == 2
    assert report["blocked_count"] == 0
    assert report["failed_count"] == 0
    assert report["refreshed_raw_count"] == 2
    assert report["force_recrawl_detected"] is True
    assert report["unknown_title_count"] == 1
    assert report["unknown_company_count"] == 1
    assert report["existing_clean_link_count"] == 1
    assert report["raw_to_clean_pct"] == 50.0
    assert report["mvp_usable_raw_count"] == 1
    assert report["mvp_usable_pct"] == 50.0
    assert report["blocked_with_existing_clean_count"] == 0
    assert report["avg_raw_markdown_length"] > 0
    assert report["first_seen_at"] is not None
    assert report["last_crawled_at"] is not None
    topcv_metrics = report["topcv_section_metrics"]
    assert topcv_metrics["css_row_count"] == 1
    assert topcv_metrics["rows_with_section_sources"] == 1
    assert topcv_metrics["rows_with_any_structured_sections"] == 1
    assert topcv_metrics["rows_with_all_structured_sections"] == 1
    assert topcv_metrics["average_structured_sections_per_css_row"] == 5.0
    assert topcv_metrics["extraction_version_counts"]["topcv_section_v2"] == 1
    assert topcv_metrics["section_presence_counts"]["description"] == 1
    assert "application_method" not in topcv_metrics["section_presence_counts"]
    assert topcv_metrics["section_source_counts"]["description"]["css_selected_job_content"] == 1
    assert len(report["audit_error_counts"]) == 3
    assert len(report["recent_failure_reason_counts"]) == 3
    assert len(report["recent_crawler_audits"]) == 3
    assert all(audit.crawl_run_id == "run-a" for audit in report["recent_crawler_audits"])
    assert all(error_type != "browser_error" for error_type, _ in report["audit_error_counts"])
    assert any(reason == "blocked_or_empty_content" for reason, _ in report["recent_failure_reason_counts"])
    assert any(row["source_seed_url"].endswith("data-scientist?sba=1") for row in report["source_seed_health"])
    assert any(row["usable_raw_count"] == 2 for row in report["source_seed_health"])
    assert any(row["skipped_count"] == 1 for row in report["source_seed_health"])
    assert any(row["refreshed_count"] == 2 for row in report["source_seed_health"])
    assert any(row["first_seen_at"] is not None for row in report["source_seed_health"])
    assert any(row["last_crawled_at"] is not None for row in report["source_seed_health"])

    rendered = format_crawl_quality_report(report)
    assert "Crawl Quality Report (crawl_run_id=run-a)" in rendered
    assert "css_success_count: 1" in rendered
    assert "refreshed_raw_count: 2" in rendered
    assert "note: refreshed rows were detected; this run likely recrawled existing URLs." in rendered
    assert "raw_to_clean_pct: 50.00%" in rendered
    assert "mvp_usable_raw_count: 1" in rendered
    assert "mvp_usable_pct: 50.00%" in rendered
    assert "topcv_section_metrics:" in rendered
    assert "extraction_version_counts:" in rendered
    assert "section_presence_counts:" in rendered
    assert "recent_failure_reason_counts:" in rendered
    assert "source_seed_health:" in rendered


def test_build_crawl_quality_report_warns_when_blocked_rows_have_existing_clean_jobs(test_db_session):
    blocked_raw = RawJobDB(
        url="https://example.com/job/blocked-current",
        crawl_run_id="run-b",
        title="Unknown (RAW)",
        company="Unknown (RAW)",
        location="Unknown",
        full_json_dump={"error": "CSS extraction failed", "is_blocked": True, "blocked_reason": "blocked_or_empty_content"},
        status="blocked",
        extraction_method="raw",
        raw_markdown="blocked markdown",
    )
    test_db_session.add(blocked_raw)
    test_db_session.flush()

    clean = CleanJobDB(
        raw_job_id=blocked_raw.id,
        standardized_title="Blocked But Previously Clean",
        job_level="Mid",
        is_internship=False,
        cities=["Hanoi"],
        tech_stack=["Python"],
        technical_competencies=[],
        domain_knowledge=["Data"],
    )
    test_db_session.add(clean)
    test_db_session.commit()

    report = build_crawl_quality_report(test_db_session, crawl_run_id="run-b", recent_limit=5)

    assert report["blocked_count"] == 1
    assert report["blocked_with_existing_clean_count"] == 1
    rendered = format_crawl_quality_report(report)
    assert "warning: blocked rows can still have existing clean jobs from earlier successful crawls." in rendered


def test_build_crawl_quality_report_includes_crawl_skipped_rows_in_recent_crawler_audits(test_db_session):
    test_db_session.add(
        RawJobDB(
            url="https://example.com/job/legacy-null-crawl",
            crawl_run_id="run-skipped",
            title="Legacy Null Crawl",
            company="Legacy Co",
            location="Remote",
            full_json_dump={"legacy": True},
            status="pending",
            extraction_method="css",
            source_seed_url="https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
        )
    )
    test_db_session.add(
        AuditJobDB(
            url="https://example.com/job/skipped",
            crawl_run_id="run-skipped",
            source_seed_url="https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
            error_type="CRAWL_SKIPPED",
            error_message="recently_blocked_cooldown",
        )
    )
    test_db_session.commit()

    report = build_crawl_quality_report(test_db_session, crawl_run_id="run-skipped", recent_limit=5)

    assert any(error_type == "CRAWL_SKIPPED" for error_type, _ in report["audit_error_counts"])
    assert any(reason == "recently_blocked_cooldown" for reason, _ in report["recent_failure_reason_counts"])
    assert any(audit.error_type == "CRAWL_SKIPPED" for audit in report["recent_crawler_audits"])
    assert report["first_seen_at"] is not None
    assert report["last_crawled_at"] is None


def test_build_crawl_quality_report_groups_multiple_seed_health_rows(test_db_session):
    ai_seed = "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"
    ds_seed = "https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1"

    test_db_session.add_all(
        [
            RawJobDB(
                url="https://example.com/job/ai-1",
                crawl_run_id="run-multi",
                source_seed_url=ai_seed,
                title="AI Engineer",
                company="AI Co",
                location="Remote",
                full_json_dump={"title": "AI Engineer", "info": "A" * 250},
                status="pending",
                extraction_method="css",
                created_at=datetime.now(timezone.utc) - timedelta(hours=2),
                updated_at=datetime.now(timezone.utc) - timedelta(hours=1),
                last_crawled_at=datetime.now(timezone.utc) - timedelta(hours=1),
            ),
            RawJobDB(
                url="https://example.com/job/ds-1",
                crawl_run_id="run-multi",
                source_seed_url=ds_seed,
                title="Unknown (RAW)",
                company="Unknown (RAW)",
                location="Unknown",
                full_json_dump={"error": "CSS extraction failed", "is_blocked": False, "blocked_reason": None},
                status="pending",
                extraction_method="raw",
                raw_markdown="raw markdown " * 10,
                created_at=datetime.now(timezone.utc) - timedelta(hours=1),
                updated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
                last_crawled_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            ),
        ]
    )
    test_db_session.commit()

    report = build_crawl_quality_report(test_db_session, crawl_run_id="run-multi", recent_limit=5)

    assert len(report["source_seed_health"]) == 2
    assert {row["source_seed_url"] for row in report["source_seed_health"]} == {ai_seed, ds_seed}
    assert any(row["css_success_count"] == 1 for row in report["source_seed_health"])
    assert any(row["raw_fallback_count"] == 1 for row in report["source_seed_health"])
    assert any(row["attempted_count"] == 1 for row in report["source_seed_health"])


def test_build_crawl_quality_report_handles_old_shallow_css_payload_without_section_provenance(test_db_session):
    test_db_session.add(
        RawJobDB(
            url="https://example.com/job/legacy-css",
            crawl_run_id="run-legacy",
            source_seed_url="https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
            title="Legacy CSS",
            company="Legacy Co",
            location="Hanoi",
            full_json_dump={"title": "Legacy CSS", "info": "A" * 240},
            status="pending",
            extraction_method="css",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            last_crawled_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
    )
    test_db_session.commit()

    report = build_crawl_quality_report(test_db_session, crawl_run_id="run-legacy", recent_limit=5)

    topcv_metrics = report["topcv_section_metrics"]
    assert topcv_metrics["css_row_count"] == 1
    assert topcv_metrics["rows_with_section_sources"] == 0
    assert topcv_metrics["rows_with_any_structured_sections"] == 0
    assert topcv_metrics["rows_with_all_structured_sections"] == 0
    assert topcv_metrics["extraction_version_counts"]["unknown"] == 1
    assert "application_method" not in topcv_metrics["section_presence_counts"]
    assert all(count == 0 for count in topcv_metrics["section_presence_counts"].values())


def test_build_crawl_quality_report_counts_mvp_usable_legacy_info_only_rows(test_db_session):
    test_db_session.add(
        RawJobDB(
            url="https://example.com/job/mvp-legacy-info",
            crawl_run_id="run-mvp",
            source_seed_url="https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
            title="Legacy Title",
            company="Legacy Co",
            location="Hanoi",
            full_json_dump={
                "info": (
                    "Mô tả công việc\n"
                    "Legacy description.\n\n"
                    "Yêu cầu ứng viên\n"
                    "Legacy requirements."
                )
            },
            status="pending",
            extraction_method="raw",
            raw_markdown="Legacy markdown fallback that should not be required.",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            last_crawled_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
    )
    test_db_session.commit()

    report = build_crawl_quality_report(test_db_session, crawl_run_id="run-mvp", recent_limit=5)

    assert report["total_raw_jobs"] == 1
    assert report["mvp_usable_raw_count"] == 1
    assert report["mvp_usable_pct"] == 100.0
