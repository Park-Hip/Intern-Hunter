from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.internhunter.storage.models import AuditJobDB, RawJobDB
from src.internhunter.storage.session import SessionLocal


DEFAULT_EXPORT_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "crawl_samples" / "topcv"
DEFAULT_STATUSES = ["pending"]


@dataclass
class ExportResult:
    raw_job_id: int
    url: str
    output_dir: str
    exported_files: list[str]
    missing_fields: list[str]


def _slugify(value: str | None) -> str:
    if not value:
        return "unknown"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return slug.lower() or "unknown"


def _safe_filename(raw_job: RawJobDB) -> str:
    job_id_match = re.search(r"(\d+)(?:\.html)?$", raw_job.url)
    job_id = job_id_match.group(1) if job_id_match else f"raw-{raw_job.id}"
    return f"{raw_job.id:06d}_{job_id}_{_slugify(raw_job.title or raw_job.company or raw_job.url)}"


def _row_to_jsonable_dict(row: RawJobDB) -> dict:
    return {
        "raw_job_id": row.id,
        "crawl_run_id": row.crawl_run_id,
        "source_seed_url": row.source_seed_url,
        "url": row.url,
        "status": row.status,
        "extraction_method": row.extraction_method,
        "title": row.title,
        "company": row.company,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "last_crawled_at": row.last_crawled_at.isoformat() if row.last_crawled_at else None,
    }


def _load_latest_audit(session, url: str, crawl_run_id: str | None) -> AuditJobDB | None:
    query = session.query(AuditJobDB).filter(AuditJobDB.url == url)
    if crawl_run_id:
        query = query.filter(AuditJobDB.crawl_run_id == crawl_run_id)
    return query.order_by(AuditJobDB.created_at.desc(), AuditJobDB.id.desc()).first()


def _select_raw_jobs(
    session,
    crawl_run_id: str,
    statuses: list[str] | None = None,
    extraction_methods: list[str] | None = None,
    limit: int | None = None,
) -> list[RawJobDB]:
    query = session.query(RawJobDB).filter(RawJobDB.crawl_run_id == crawl_run_id)
    if statuses:
        query = query.filter(RawJobDB.status.in_(statuses))
    if extraction_methods:
        query = query.filter(RawJobDB.extraction_method.in_(extraction_methods))

    query = query.order_by(
        (RawJobDB.extraction_method == "css").desc(),
        (RawJobDB.extraction_method == "raw").desc(),
        RawJobDB.created_at.asc(),
        RawJobDB.id.asc(),
    )

    if limit is not None:
        query = query.limit(limit)

    return query.all()


def export_crawl_fixtures(
    session,
    crawl_run_id: str,
    output_root: Path = DEFAULT_EXPORT_ROOT,
    statuses: list[str] | None = None,
    extraction_methods: list[str] | None = None,
    limit: int | None = None,
) -> dict:
    statuses = statuses if statuses is not None else DEFAULT_STATUSES
    output_dir = output_root / crawl_run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_jobs = _select_raw_jobs(
        session,
        crawl_run_id=crawl_run_id,
        statuses=statuses,
        extraction_methods=extraction_methods,
        limit=limit,
    )

    exported: list[ExportResult] = []
    skipped_count = 0

    for row in raw_jobs:
        job_dir = output_dir / _safe_filename(row)
        job_dir.mkdir(parents=True, exist_ok=True)

        exported_files: list[str] = []
        missing_fields: list[str] = []
        metadata = _row_to_jsonable_dict(row)

        metadata["export_dir"] = str(job_dir)
        metadata["missing_fields"] = []

        latest_audit = _load_latest_audit(session, row.url, crawl_run_id)
        html_content = row.html_content or (
            latest_audit.html_content if latest_audit and latest_audit.html_content else None
        )
        screenshot_path = row.screenshot_path or (
            latest_audit.screenshot_path if latest_audit and latest_audit.screenshot_path else None
        )

        if html_content:
            html_path = job_dir / "raw.html"
            html_path.write_text(html_content, encoding="utf-8")
            exported_files.append(html_path.name)
            metadata["html_path"] = html_path.name
        else:
            missing_fields.append("html")
            metadata["html_path"] = None

        if row.raw_markdown:
            md_path = job_dir / "raw_markdown.txt"
            md_path.write_text(row.raw_markdown, encoding="utf-8")
            exported_files.append(md_path.name)
            metadata["raw_markdown_path"] = md_path.name
        else:
            missing_fields.append("raw_markdown")
            metadata["raw_markdown_path"] = None

        if row.full_json_dump is not None:
            json_path = job_dir / "full_json_dump.json"
            json_path.write_text(json.dumps(row.full_json_dump, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            exported_files.append(json_path.name)
            metadata["full_json_dump_path"] = json_path.name
        else:
            missing_fields.append("full_json_dump")
            metadata["full_json_dump_path"] = None

        if screenshot_path:
            source_path = Path(screenshot_path)
            if source_path.exists():
                screenshot_target = job_dir / source_path.name
                shutil.copy2(source_path, screenshot_target)
                exported_files.append(screenshot_target.name)
                metadata["screenshot_path"] = screenshot_target.name
            else:
                missing_fields.append("screenshot_missing_source_file")
                metadata["screenshot_path"] = screenshot_path
        else:
            missing_fields.append("screenshot")
            metadata["screenshot_path"] = None

        metadata["missing_fields"] = missing_fields
        metadata_path = job_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        exported_files.append(metadata_path.name)

        exported.append(
            ExportResult(
                raw_job_id=row.id,
                url=row.url,
                output_dir=str(job_dir),
                exported_files=exported_files,
                missing_fields=missing_fields,
            )
        )

    summary = {
        "crawl_run_id": crawl_run_id,
        "output_dir": str(output_dir),
        "exported_count": len(exported),
        "skipped_count": skipped_count,
        "urls": [item.url for item in exported],
        "results": [asdict(item) for item in exported],
    }

    summary_path = output_dir / "export_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export TopCV crawl artifacts into fixture files.")
    parser.add_argument("--crawl-run-id", required=True, help="Run id to export from.")
    parser.add_argument("--status", action="append", dest="statuses", help="Optional status filter. May be repeated.")
    parser.add_argument(
        "--extraction-method",
        action="append",
        dest="extraction_methods",
        help="Optional extraction-method filter. May be repeated.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of rows to export.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_EXPORT_ROOT),
        help="Base directory for exported fixtures.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as session:
        summary = export_crawl_fixtures(
            session=session,
            crawl_run_id=args.crawl_run_id,
            output_root=Path(args.output_root),
            statuses=args.statuses,
            extraction_methods=args.extraction_methods,
            limit=args.limit,
        )

    print(f"exported_count: {summary['exported_count']}")
    print(f"skipped_count: {summary['skipped_count']}")
    print(f"output_dir: {summary['output_dir']}")
    print("exported_urls:")
    for url in summary["urls"]:
        print(f"  - {url}")
    if summary["exported_count"] > 0:
        print("Reminder: add this sample to fixture_manifest.json before selector tuning.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
