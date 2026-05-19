from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.internhunter.common.logging import configure_logging, get_logger
from src.internhunter.storage.models import RawJobDB
from src.internhunter.storage.session import SessionLocal
from src.scripts.export_crawl_fixtures import export_crawl_fixtures
from src.internhunter.crawler.crawl import Crawler


logger = get_logger(__name__)
DEFAULT_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "crawl_samples" / "topcv"
ALLOWED_LAYOUT_FAMILIES = {
    "standard_topcv",
    "branded_topcv",
    "raw_fallback",
    "blocked",
    "unknown",
}


def _slugify(value: str | None) -> str:
    if not value:
        return "unknown"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
    return slug.lower() or "unknown"


def _brand_from_url(url: str) -> str:
    match = re.search(r"/brand/([^/]+)/", url, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return "manual_fixture"


def _build_manifest_entry(
    *,
    crawl_run_id: str,
    sample_dir: str,
    url: str,
    layout_family: str,
    expected_status: str,
    expected_extraction_method: str,
    notes: str,
) -> dict:
    return {
        "crawl_run_id": crawl_run_id,
        "sample_dir": sample_dir,
        "url": url,
        "layout_family": layout_family,
        "expected_status": expected_status,
        "expected_extraction_method": expected_extraction_method,
        "notes": notes,
    }


def _append_manifest_entry(manifest_path: Path, entry: dict) -> None:
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"samples": []}
    manifest.setdefault("samples", []).append(entry)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl one explicit TopCV URL and export it as a fixture sample.")
    parser.add_argument("--url", required=True, help="TopCV job URL to crawl.")
    parser.add_argument("--layout-family", default="unknown", choices=sorted(ALLOWED_LAYOUT_FAMILIES))
    parser.add_argument("--source-seed-url", default="manual_fixture", help="Manual source attribution label.")
    parser.add_argument("--crawl-run-id", default=None, help="Optional crawl run id. Generated if omitted.")
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="Append the generated sample entry to fixture_manifest.json.",
    )
    return parser.parse_args()


async def _crawl_single_url(url: str, crawl_run_id: str, source_seed_url: str) -> tuple[int, int]:
    crawler = Crawler()
    return await crawler.crawl_jobs(
        [{"url": url, "source_seed_url": source_seed_url}],
        crawl_run_id,
        force_recrawl=True,
    )


def _load_exported_job_dir(output_dir: Path) -> Path | None:
    if not output_dir.exists():
        return None
    job_dirs = sorted(path for path in output_dir.iterdir() if path.is_dir())
    return job_dirs[0] if job_dirs else None


def main() -> int:
    args = parse_args()
    configure_logging()
    crawl_run_id = args.crawl_run_id or str(uuid.uuid4())[:8]

    logger.info(
        "Starting one-url fixture crawl",
        crawl_run_id=crawl_run_id,
        url=args.url,
        layout_family=args.layout_family,
        source_seed_url=args.source_seed_url,
    )

    saved_count, failed_count = asyncio.run(_crawl_single_url(args.url, crawl_run_id, args.source_seed_url))

    try:
        with SessionLocal() as session:
            summary = export_crawl_fixtures(
                session=session,
                crawl_run_id=crawl_run_id,
                output_root=DEFAULT_FIXTURE_ROOT,
                statuses=["pending", "blocked"],
            )

            raw_job = (
                session.query(RawJobDB)
                .filter(RawJobDB.crawl_run_id == crawl_run_id, RawJobDB.url == args.url)
                .order_by(RawJobDB.id.desc())
                .first()
            )
    except Exception as exc:
        print(f"database_unavailable: {exc}")
        print(f"crawl_run_id: {crawl_run_id}")
        print(f"url: {args.url}")
        print(f"saved_count: {saved_count}")
        print(f"failed_count: {failed_count}")
        print("manifest_entry: unavailable until the crawl can be persisted and exported")
        return 1

    output_dir = Path(summary["output_dir"])
    job_dir = _load_exported_job_dir(output_dir)
    manifest_entry = _build_manifest_entry(
        crawl_run_id=crawl_run_id,
        sample_dir=f"{crawl_run_id}/{job_dir.name if job_dir else _slugify(args.url)}",
        url=args.url,
        layout_family=args.layout_family,
        expected_status=raw_job.status if raw_job else "unknown",
        expected_extraction_method=raw_job.extraction_method if raw_job else "unknown",
        notes=f"manual {args.layout_family} fixture for {_brand_from_url(args.url)}",
    )

    if args.update_manifest:
        manifest_path = DEFAULT_FIXTURE_ROOT / "fixture_manifest.json"
        _append_manifest_entry(manifest_path, manifest_entry)
        print(f"manifest_updated: {manifest_path}")

    print(f"crawl_run_id: {crawl_run_id}")
    print(f"raw_job_id: {raw_job.id if raw_job else 'unknown'}")
    print(f"url: {args.url}")
    print(f"status: {raw_job.status if raw_job else 'unknown'}")
    print(f"extraction_method: {raw_job.extraction_method if raw_job else 'unknown'}")
    print(f"title: {raw_job.title if raw_job else 'unknown'}")
    print(f"company: {raw_job.company if raw_job else 'unknown'}")
    print(f"saved_count: {saved_count}")
    print(f"failed_count: {failed_count}")
    print(f"output_dir: {output_dir}")
    print(f"raw.html_exists: {bool(job_dir and (job_dir / 'raw.html').exists())}")
    print(f"raw_markdown.txt_exists: {bool(job_dir and (job_dir / 'raw_markdown.txt').exists())}")
    print(f"screenshot_exists: {bool(job_dir and any(path.name.endswith('.png') for path in job_dir.iterdir())) if job_dir else False}")
    print("manifest_entry:")
    print(json.dumps(manifest_entry, ensure_ascii=False, indent=2))
    print("Add this sample to fixture_manifest.json before selector tuning.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
