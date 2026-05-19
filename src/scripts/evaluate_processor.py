import argparse
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.internhunter.storage.repositories.etl import ETLRepository
from src.internhunter.extraction.job_processor import JobProcessor
from src.scripts.crawl_quality_report import _is_mvp_usable_raw_job


def _ensure_utf8_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic TopCV processor evaluation without LLM calls.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of pending raw jobs to evaluate.")
    parser.add_argument("--crawl-run-id", dest="crawl_run_id", default=None, help="Optional crawl run id to scope raw jobs.")
    return parser.parse_args()


async def main_async() -> int:
    _ensure_utf8_streams()
    args = parse_args()
    repo = ETLRepository()
    pending_jobs = repo.fetch_pending_raw_jobs(limit=args.limit, crawl_run_id=args.crawl_run_id)
    mvp_usable_raw_count = sum(1 for job in pending_jobs if _is_mvp_usable_raw_job(job))
    mvp_usable_pct = round((100.0 * mvp_usable_raw_count / len(pending_jobs)), 2) if pending_jobs else 0.0

    processor = JobProcessor()
    success_count, fail_count = await processor.process_jobs_deterministic(
        limit=args.limit,
        crawl_run_id=args.crawl_run_id,
    )
    print(f"deterministic_processed: success={success_count} failed={fail_count}")
    print(f"mvp_usable_pending_raw: count={mvp_usable_raw_count} pct={mvp_usable_pct:.2f}")
    return 0


def main() -> int:
    import asyncio

    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
