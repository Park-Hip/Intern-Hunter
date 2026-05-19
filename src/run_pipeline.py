import argparse
import asyncio
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.internhunter.orchestration.ingestion_flow import job_ingestion_flow


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="InternHunter ETL Pipeline")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of job detail pages to crawl and process in the local MVP slice",
    )
    parser.add_argument(
        "--force-recrawl",
        action="store_true",
        help="Dev-only option to re-crawl already-seen links for local MVP testing",
    )
    validation_group = parser.add_mutually_exclusive_group()
    validation_group.add_argument(
        "--enable-llm-validation",
        "--strict-llm-validation",
        dest="enable_llm_validation",
        action="store_true",
        help="Opt in to LLM job-validity validation. Off by default for the MVP pipeline.",
    )
    validation_group.add_argument(
        "--skip-llm-validation",
        action="store_true",
        help="Compatibility alias for the default MVP behavior; validation is already off by default.",
    )
    parser.add_argument(
        "--crawl-only",
        action="store_true",
        help="Dev-only option to stop after crawling and skip job processing",
    )
    return parser


def _should_skip_llm_validation(*, enable_llm_validation: bool, skip_llm_validation: bool) -> bool:
    return not enable_llm_validation


async def run_full_pipeline(
    limit: int = 10,
    force_recrawl: bool = False,
    skip_llm_validation: bool = True,
    crawl_only: bool = False,
):
    """Compatibility alias for the current ingestion flow.

    The MVP default is to skip LLM job-validity validation unless the caller
    explicitly opts back in.
    """
    await job_ingestion_flow(
        limit=limit,
        force_recrawl=force_recrawl,
        skip_llm_validation=skip_llm_validation,
        crawl_only=crawl_only,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    skip_llm_validation = _should_skip_llm_validation(
        enable_llm_validation=args.enable_llm_validation,
        skip_llm_validation=args.skip_llm_validation,
    )

    asyncio.run(
        job_ingestion_flow(
            limit=args.limit,
            force_recrawl=args.force_recrawl,
            skip_llm_validation=skip_llm_validation,
            crawl_only=args.crawl_only,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
