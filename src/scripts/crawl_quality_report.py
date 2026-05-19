import argparse
import json
import os
import sys
from collections import Counter
from typing import Any

from sqlalchemy import case, func, or_, select

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.internhunter.llm.base import LLMProvider
from src.internhunter.storage.models import AuditJobDB, CleanJobDB, RawJobDB
from src.internhunter.storage.session import SessionLocal


_CRAWLER_AUDIT_TYPES = ["BOT_DETECTED", "CRAWL_FAILED", "CRAWL_SKIPPED"]

TOPCV_SECTION_FIELDS = (
    "description",
    "requirements",
    "benefits",
    "work_location",
    "working_time",
)

TOPCV_SECTION_SOURCE_LABELS = (
    "css_selected_job_content",
    "raw_markdown",
    "html_text",
    "unknown",
)

MVP_REQUIRED_FIELDS = (
    "title",
    "company",
    "description",
    "requirements",
)


def _is_unknown_text(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().lower()
    return normalized.startswith("unknown")


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _scope_raw_jobs_query(session, crawl_run_id: str | None):
    query = session.query(RawJobDB)
    if crawl_run_id:
        query = query.filter(RawJobDB.crawl_run_id == crawl_run_id)
    return query


def _scope_audit_jobs_query(session, crawl_run_id: str | None):
    query = session.query(AuditJobDB)
    if crawl_run_id:
        query = query.filter(AuditJobDB.crawl_run_id == crawl_run_id)
    return query


def _coerce_full_json_dump(full_json_dump) -> dict[str, Any]:
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


def _build_topcv_section_metrics(raw_jobs_query) -> dict[str, Any]:
    presence_counts = {section: 0 for section in TOPCV_SECTION_FIELDS}
    source_counts = {
        section: Counter({source: 0 for source in TOPCV_SECTION_SOURCE_LABELS})
        for section in TOPCV_SECTION_FIELDS
    }
    extraction_version_counts: Counter[str] = Counter()

    css_rows = (
        raw_jobs_query.filter(
            RawJobDB.status == "pending",
            func.lower(func.coalesce(RawJobDB.extraction_method, "")) == "css",
        )
        .all()
    )

    css_row_count = len(css_rows)
    rows_with_section_sources = 0
    rows_with_any_structured_sections = 0
    rows_with_all_structured_sections = 0
    total_structured_sections = 0

    for row in css_rows:
        payload = _coerce_full_json_dump(row.full_json_dump)
        if not payload:
            extraction_version_counts["unknown"] += 1
            continue

        extraction_version_counts[payload.get("extraction_version") or "unknown"] += 1
        section_sources = payload.get("section_sources")
        if not isinstance(section_sources, dict):
            section_sources = {}
        if any(section_sources.get(section) for section in TOPCV_SECTION_FIELDS):
            rows_with_section_sources += 1

        row_structured_section_count = 0
        for section in TOPCV_SECTION_FIELDS:
            if payload.get(section):
                presence_counts[section] += 1
                row_structured_section_count += 1
                source_label = section_sources.get(section) or "unknown"
                source_counts[section][source_label] += 1

        total_structured_sections += row_structured_section_count
        if row_structured_section_count > 0:
            rows_with_any_structured_sections += 1
        if row_structured_section_count == len(TOPCV_SECTION_FIELDS):
            rows_with_all_structured_sections += 1

    average_structured_sections_per_css_row = (
        round(total_structured_sections / css_row_count, 2) if css_row_count else 0.0
    )

    return {
        "css_row_count": css_row_count,
        "rows_with_section_sources": rows_with_section_sources,
        "rows_with_any_structured_sections": rows_with_any_structured_sections,
        "rows_with_all_structured_sections": rows_with_all_structured_sections,
        "average_structured_sections_per_css_row": average_structured_sections_per_css_row,
        "extraction_version_counts": dict(extraction_version_counts),
        "section_presence_counts": presence_counts,
        "section_source_counts": {section: dict(counts) for section, counts in source_counts.items()},
    }


def _extract_mvp_job_fields(raw_job: Any) -> dict[str, str | None]:
    payload = _coerce_full_json_dump(getattr(raw_job, "full_json_dump", None))
    title = _clean_text(getattr(raw_job, "title", None)) or _clean_text(payload.get("title"))
    company = _clean_text(getattr(raw_job, "company", None)) or _clean_text(payload.get("company"))

    description = _clean_text(payload.get("description"))
    requirements = _clean_text(payload.get("requirements"))

    if not description or not requirements:
        fallback_source = (
            _clean_text(payload.get("info"))
            or _clean_text(getattr(raw_job, "raw_markdown", None))
            or ""
        )
        legacy_description, legacy_requirement, _ = LLMProvider._extract_info(fallback_source)
        description = description or _clean_text(legacy_description)
        requirements = requirements or _clean_text(legacy_requirement)

    return {
        "title": title,
        "company": company,
        "description": description,
        "requirements": requirements,
    }


def _is_mvp_usable_raw_job(raw_job: Any) -> bool:
    fields = _extract_mvp_job_fields(raw_job)
    return all(
        field_value
        and not _is_unknown_text(field_value)
        for field_value in (
            fields["title"],
            fields["company"],
            fields["description"],
            fields["requirements"],
        )
    )


def _build_mvp_usability_metrics(raw_jobs_query) -> dict[str, Any]:
    raw_jobs = raw_jobs_query.all()
    mvp_usable_raw_count = sum(1 for raw_job in raw_jobs if _is_mvp_usable_raw_job(raw_job))
    total_raw_jobs = len(raw_jobs)
    mvp_usable_pct = round((100.0 * mvp_usable_raw_count / total_raw_jobs), 2) if total_raw_jobs else 0.0
    return {
        "mvp_usable_raw_count": mvp_usable_raw_count,
        "mvp_usable_pct": mvp_usable_pct,
    }


def build_crawl_quality_report(session, crawl_run_id: str | None = None, recent_limit: int = 5) -> dict[str, Any]:
    raw_jobs_query = _scope_raw_jobs_query(session, crawl_run_id)
    audit_jobs_query = _scope_audit_jobs_query(session, crawl_run_id)

    total_raw_jobs = raw_jobs_query.count()
    css_success_count = (
        raw_jobs_query.filter(
            RawJobDB.status == "pending",
            func.lower(func.coalesce(RawJobDB.extraction_method, "")) == "css",
        ).count()
    )
    raw_fallback_pending_count = (
        raw_jobs_query.filter(
            RawJobDB.status == "pending",
            func.lower(func.coalesce(RawJobDB.extraction_method, "")) == "raw",
        ).count()
    )
    blocked_count = raw_jobs_query.filter(RawJobDB.status == "blocked").count()
    failed_count = raw_jobs_query.filter(RawJobDB.status == "failed").count()
    current_usable_raw_count = css_success_count + raw_fallback_pending_count
    mvp_usability_metrics = _build_mvp_usability_metrics(raw_jobs_query)
    refreshed_raw_count = raw_jobs_query.filter(
        RawJobDB.last_crawled_at.isnot(None),
        RawJobDB.created_at.isnot(None),
        RawJobDB.last_crawled_at > RawJobDB.created_at,
    ).count()
    unknown_title_count = raw_jobs_query.filter(or_(RawJobDB.title.is_(None), func.lower(RawJobDB.title).like("unknown%"))).count()
    unknown_company_count = raw_jobs_query.filter(or_(RawJobDB.company.is_(None), func.lower(RawJobDB.company).like("unknown%"))).count()
    avg_raw_markdown_length = raw_jobs_query.with_entities(func.avg(func.length(RawJobDB.raw_markdown))).scalar()
    first_seen_at = raw_jobs_query.with_entities(func.min(RawJobDB.created_at)).scalar()
    last_crawled_at = raw_jobs_query.with_entities(func.max(RawJobDB.last_crawled_at)).scalar()
    topcv_section_metrics = _build_topcv_section_metrics(raw_jobs_query)

    raw_job_ids_subquery = raw_jobs_query.with_entities(RawJobDB.id).subquery()
    existing_clean_link_count = (
        session.query(func.count(CleanJobDB.id))
        .filter(CleanJobDB.raw_job_id.in_(select(raw_job_ids_subquery.c.id)))
        .scalar()
    ) or 0
    blocked_with_existing_clean_count = (
        session.query(func.count(CleanJobDB.id))
        .join(RawJobDB, RawJobDB.id == CleanJobDB.raw_job_id)
        .filter(RawJobDB.status == "blocked")
    )
    if crawl_run_id:
        blocked_with_existing_clean_count = blocked_with_existing_clean_count.filter(RawJobDB.crawl_run_id == crawl_run_id)
    blocked_with_existing_clean_count = blocked_with_existing_clean_count.scalar() or 0
    raw_to_clean_pct = round((100.0 * existing_clean_link_count / total_raw_jobs), 2) if total_raw_jobs else 0.0

    audit_error_counts = (
        audit_jobs_query.with_entities(AuditJobDB.error_type, func.count(AuditJobDB.id))
        .group_by(AuditJobDB.error_type)
        .order_by(func.count(AuditJobDB.id).desc())
        .all()
    )
    recent_crawler_audits = (
        audit_jobs_query
        .filter(AuditJobDB.error_type.in_(_CRAWLER_AUDIT_TYPES))
        .order_by(AuditJobDB.created_at.desc())
        .limit(recent_limit)
        .all()
    )
    recent_failure_reason_counts = (
        audit_jobs_query.with_entities(AuditJobDB.error_message, func.count(AuditJobDB.id))
        .filter(AuditJobDB.error_type.in_(_CRAWLER_AUDIT_TYPES))
        .group_by(AuditJobDB.error_message)
        .order_by(func.count(AuditJobDB.id).desc())
        .all()
    )

    source_label = func.coalesce(RawJobDB.source_seed_url, "unknown")
    source_rows = (
        raw_jobs_query.with_entities(
            source_label.label("source_seed_url"),
            func.count(RawJobDB.id).label("attempted_count"),
            func.sum(case((RawJobDB.status == "blocked", 1), else_=0)).label("blocked_count"),
            func.sum(case((RawJobDB.status == "failed", 1), else_=0)).label("failed_count"),
            func.sum(
                case(
                    (
                        (RawJobDB.status == "pending")
                        & (func.lower(func.coalesce(RawJobDB.extraction_method, "")) == "css"),
                        1,
                    ),
                    else_=0,
                )
            ).label("css_success_count"),
            func.sum(
                case(
                    (
                        (RawJobDB.status == "pending")
                        & (func.lower(func.coalesce(RawJobDB.extraction_method, "")) == "raw"),
                        1,
                    ),
                    else_=0,
                )
            ).label("raw_fallback_count"),
            func.sum(
                case(
                    (
                        (RawJobDB.last_crawled_at.isnot(None))
                        & (RawJobDB.created_at.isnot(None))
                        & (RawJobDB.last_crawled_at > RawJobDB.created_at),
                        1,
                    ),
                    else_=0,
                )
            ).label("refreshed_count"),
            func.min(RawJobDB.created_at).label("first_seen_at"),
            func.max(RawJobDB.last_crawled_at).label("last_crawled_at"),
        )
        .group_by(source_label)
        .all()
    )

    skipped_rows = (
        audit_jobs_query.with_entities(
            func.coalesce(AuditJobDB.source_seed_url, "unknown").label("source_seed_url"),
            func.count(AuditJobDB.id).label("skipped_count"),
        )
        .filter(AuditJobDB.error_type == "CRAWL_SKIPPED")
        .group_by(func.coalesce(AuditJobDB.source_seed_url, "unknown"))
        .all()
    )
    skipped_map = {source_seed_url: skipped_count for source_seed_url, skipped_count in skipped_rows}

    source_seed_health = []
    seen_sources: set[str] = set()
    for row in source_rows:
        source_seed_url = row.source_seed_url or "unknown"
        seen_sources.add(source_seed_url)
        attempted_count = row.attempted_count or 0
        blocked_count_source = row.blocked_count or 0
        failed_count_source = row.failed_count or 0
        css_success_count_source = row.css_success_count or 0
        raw_fallback_count_source = row.raw_fallback_count or 0
        refreshed_count_source = row.refreshed_count or 0
        skipped_count_source = skipped_map.get(source_seed_url, 0)
        usable_count_source = css_success_count_source + raw_fallback_count_source
        block_rate = round((100.0 * blocked_count_source / attempted_count), 2) if attempted_count else 0.0
        usable_rate = round((100.0 * usable_count_source / attempted_count), 2) if attempted_count else 0.0
        source_seed_health.append(
            {
                "source_seed_url": source_seed_url,
                "attempted_count": attempted_count,
                "blocked_count": blocked_count_source,
                "failed_count": failed_count_source,
                "skipped_count": skipped_count_source,
                "usable_raw_count": usable_count_source,
                "css_success_count": css_success_count_source,
                "raw_fallback_count": raw_fallback_count_source,
                "refreshed_count": refreshed_count_source,
                "block_rate": block_rate,
                "usable_rate": usable_rate,
                "first_seen_at": row.first_seen_at,
                "last_crawled_at": row.last_crawled_at,
            }
        )

    for source_seed_url, skipped_count_source in skipped_map.items():
        if source_seed_url in seen_sources:
            continue
        source_seed_health.append(
            {
                "source_seed_url": source_seed_url,
                "attempted_count": 0,
                "blocked_count": 0,
                "failed_count": 0,
                "skipped_count": skipped_count_source,
                "usable_raw_count": 0,
                "css_success_count": 0,
                "raw_fallback_count": 0,
                "refreshed_count": 0,
                "block_rate": 0.0,
                "usable_rate": 0.0,
                "first_seen_at": None,
                "last_crawled_at": None,
            }
        )

    source_seed_health.sort(key=lambda row: (-row["attempted_count"], row["source_seed_url"]))

    return {
        "crawl_run_id": crawl_run_id,
        "total_raw_jobs": total_raw_jobs,
        "css_success_count": css_success_count,
        "raw_fallback_pending_count": raw_fallback_pending_count,
        "current_usable_raw_count": current_usable_raw_count,
        **mvp_usability_metrics,
        "blocked_count": blocked_count,
        "failed_count": failed_count,
        "refreshed_raw_count": refreshed_raw_count,
        "force_recrawl_detected": refreshed_raw_count > 0,
        "unknown_title_count": unknown_title_count,
        "unknown_company_count": unknown_company_count,
        "avg_raw_markdown_length": avg_raw_markdown_length or 0.0,
        "first_seen_at": first_seen_at,
        "last_crawled_at": last_crawled_at,
        "existing_clean_link_count": existing_clean_link_count,
        "raw_to_clean_count": existing_clean_link_count,
        "raw_to_clean_pct": raw_to_clean_pct,
        "blocked_with_existing_clean_count": blocked_with_existing_clean_count,
        "audit_error_counts": audit_error_counts,
        "recent_crawler_audits": recent_crawler_audits,
        "recent_failure_reason_counts": recent_failure_reason_counts,
        "source_seed_health": source_seed_health,
        "topcv_section_metrics": topcv_section_metrics,
    }


def format_crawl_quality_report(report: dict[str, Any]) -> str:
    def fmt_num(value: Any) -> str:
        if value is None:
            return "0"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    lines = []
    title = "Crawl Quality Report"
    if report.get("crawl_run_id"):
        title += f" (crawl_run_id={report['crawl_run_id']})"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append(f"total_raw_jobs: {fmt_num(report['total_raw_jobs'])}")
    lines.append(f"css_success_count: {fmt_num(report['css_success_count'])}")
    lines.append(f"raw_fallback_pending_count: {fmt_num(report['raw_fallback_pending_count'])}")
    lines.append(f"blocked_count: {fmt_num(report['blocked_count'])}")
    lines.append(f"failed_count: {fmt_num(report['failed_count'])}")
    lines.append(f"refreshed_raw_count: {fmt_num(report['refreshed_raw_count'])}")
    if report["force_recrawl_detected"]:
        lines.append("note: refreshed rows were detected; this run likely recrawled existing URLs.")
    lines.append(f"unknown_title_count: {fmt_num(report['unknown_title_count'])}")
    lines.append(f"unknown_company_count: {fmt_num(report['unknown_company_count'])}")
    lines.append(f"avg_raw_markdown_length: {fmt_num(report['avg_raw_markdown_length'])}")
    lines.append(f"first_seen_at: {report['first_seen_at'] or 'none'}")
    lines.append(f"last_crawled_at: {report['last_crawled_at'] or 'none'}")
    lines.append(f"current_usable_raw_count: {fmt_num(report['current_usable_raw_count'])}")
    lines.append(f"mvp_usable_raw_count: {fmt_num(report['mvp_usable_raw_count'])}")
    lines.append(f"mvp_usable_pct: {fmt_num(report['mvp_usable_pct'])}%")
    lines.append(f"existing_clean_link_count: {fmt_num(report['existing_clean_link_count'])}")
    lines.append(f"raw_to_clean_pct: {fmt_num(report['raw_to_clean_pct'])}%")
    lines.append(f"blocked_with_existing_clean_count: {fmt_num(report['blocked_with_existing_clean_count'])}")
    if report["blocked_count"] > 0 and report["blocked_with_existing_clean_count"] > 0:
        lines.append("warning: blocked rows can still have existing clean jobs from earlier successful crawls.")
    lines.append("")
    lines.append("source_seed_health:")
    if report["source_seed_health"]:
        for row in report["source_seed_health"]:
            lines.append(
                "  - "
                f"{row['source_seed_url']} | attempted={row['attempted_count']} | "
                f"css_success={row['css_success_count']} | raw_fallback={row['raw_fallback_count']} | "
                f"blocked={row['blocked_count']} | failed={row['failed_count']} | skipped={row['skipped_count']} | refreshed={row['refreshed_count']} | "
                f"usable={row['usable_raw_count']} | block_rate={row['block_rate']:.2f}% | usable_rate={row['usable_rate']:.2f}% | "
                f"first_seen={row['first_seen_at'] or 'none'} | last_crawled={row['last_crawled_at'] or 'none'}"
            )
    else:
        lines.append("  - none")
    lines.append("")
    topcv_metrics = report.get("topcv_section_metrics", {})
    lines.append("topcv_section_metrics:")
    if topcv_metrics and topcv_metrics.get("css_row_count", 0):
        lines.append(f"  css_row_count: {fmt_num(topcv_metrics['css_row_count'])}")
        lines.append(f"  rows_with_section_sources: {fmt_num(topcv_metrics['rows_with_section_sources'])}")
        lines.append(f"  rows_with_any_structured_sections: {fmt_num(topcv_metrics['rows_with_any_structured_sections'])}")
        lines.append(f"  rows_with_all_structured_sections: {fmt_num(topcv_metrics['rows_with_all_structured_sections'])}")
        lines.append(
            "  average_structured_sections_per_css_row: "
            f"{fmt_num(topcv_metrics['average_structured_sections_per_css_row'])}"
        )
        lines.append("  extraction_version_counts:")
        extraction_version_counts = topcv_metrics.get("extraction_version_counts", {})
        if extraction_version_counts:
            for version, count in extraction_version_counts.items():
                lines.append(f"    - {version}: {count}")
        else:
            lines.append("    - none")
        lines.append("  section_presence_counts:")
        for section_name in TOPCV_SECTION_FIELDS:
            lines.append(f"    - {section_name}: {topcv_metrics['section_presence_counts'].get(section_name, 0)}")
        lines.append("  section_source_counts:")
        for section_name in TOPCV_SECTION_FIELDS:
            source_counts = topcv_metrics["section_source_counts"].get(section_name, {})
            counts_text = " | ".join(
                f"{source}={source_counts.get(source, 0)}" for source in TOPCV_SECTION_SOURCE_LABELS
            )
            lines.append(f"    - {section_name}: {counts_text}")
    else:
        lines.append("  - none")
    lines.append("")
    lines.append("audit_error_counts:")
    if report["audit_error_counts"]:
        for error_type, count in report["audit_error_counts"]:
            lines.append(f"  - {error_type or 'UNKNOWN'}: {count}")
    else:
        lines.append("  - none")
    lines.append("")
    lines.append("recent_failure_reason_counts:")
    if report["recent_failure_reason_counts"]:
        for reason, count in report["recent_failure_reason_counts"]:
            lines.append(f"  - {reason or 'UNKNOWN'}: {count}")
    else:
        lines.append("  - none")
    lines.append("")
    lines.append("recent_crawler_audits:")
    if report["recent_crawler_audits"]:
        for audit in report["recent_crawler_audits"]:
            lines.append(
                f"  - {audit.created_at} | {audit.error_type} | {audit.url} | "
                f"run={audit.crawl_run_id or 'UNKNOWN'} | seed={audit.source_seed_url or 'UNKNOWN'} | "
                f"{audit.error_message or ''}"
            )
    else:
        lines.append("  - none")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a TopCV crawler quality report from the database.")
    parser.add_argument("--crawl-run-id", dest="crawl_run_id", default=None, help="Optional crawl run id to scope raw_jobs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as session:
        report = build_crawl_quality_report(session, crawl_run_id=args.crawl_run_id)
        print(format_crawl_quality_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
