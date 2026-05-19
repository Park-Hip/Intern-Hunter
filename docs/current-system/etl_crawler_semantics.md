# ETL / Crawler Semantics

This note captures the current semantics of the crawler and ETL pipeline so future experiments stay easy to interpret.

## Pipeline Modes

- Full ETL: crawl, process, embed, and load clean jobs.
- Crawl-only: crawl raw jobs only, skip job processing and downstream LLM/embedding work.
- Skip LLM validation: keep processing enabled, but skip the LLM validation step inside job processing.
- Default MVP pipeline: validation is off unless you opt in with `--enable-llm-validation` (or the compatibility alias `--skip-llm-validation`).

## Current Architecture Checkpoint

- crawl-only mode works
- ordered multi-seed TopCV crawling works
- run-scoped audit reporting works
- source_seed_health reporting works
- force_recrawl semantics are clarified
- raw_jobs timestamp semantics are clarified
- successful crawl artifacts are persisted
- fixture export and manual fixture collection work
- fixture_manifest.json labels layout families
- full_json_dump contains structured TopCV core sections
  - description
  - requirements
  - benefits
  - work_location
  - working_time
- full_json_dump includes extraction_version and section_sources provenance
- JobProcessor prefers structured description / requirements / benefits over legacy info
- MVP usability metrics track the shipping bar separately from 5-section quality metrics
- Default MVP pipeline skips LLM job-validity validation unless explicitly enabled

## Stable Components

- crawl-only mode
- force_recrawl semantics
- source_seed_health
- timestamp semantics
- fixture workflow
- info fallback
- old raw_jobs backward compatibility

Recommended local crawler experiment:

```powershell
uv run python src/run_pipeline.py --limit 1 --force-recrawl --crawl-only
uv run python src/scripts/crawl_quality_report.py --crawl-run-id <run_id>
```

## Raw Job Timestamps

Raw rows are refreshed in place by URL.

- `created_at`: first discovery / first insert for that URL.
- `updated_at`: latest database row update.
- `last_crawled_at`: latest crawl attempt or refresh for that URL.
- `crawl_run_id`: latest run that touched or refreshed that row.

Recrawl semantics:

- `force_recrawl` bypasses URL dedup so already-known URLs can be selected again.
- Existing raw rows are refreshed by URL instead of creating duplicates.
- `created_at` is preserved.
- `crawl_run_id`, `updated_at`, `last_crawled_at`, and `source_seed_url` are updated.
- Recently blocked URL cooldown is still respected.
- Clean-job reprocessing is not forced automatically.

## Audit States

Crawler-related audit rows are split into separate states.

- `CRAWL_FAILED`: a crawl attempt failed.
- `BOT_DETECTED`: blocked or verification-style content was detected.
- `CRAWL_SKIPPED`: the URL was intentionally skipped, usually because it was recently blocked.
- `PROCESSING_ERROR`: downstream job processing failed after crawl, if present.

Audit rows are run-scoped when possible and should be interpreted alongside `crawl_run_id`.

## Source / Seed Visibility

Crawler rows now carry `source_seed_url` so experiments can be grouped by TopCV search seed.

The report also shows `source_seed_health`, which summarizes per seed:

- attempted count
- blocked count
- failed count
- skipped count
- usable raw count
- CSS success count
- raw fallback count
- refreshed count
- block rate
- usable rate
- first seen time
- last crawled time

## How to Read the Report

Use the scoped report first:

```powershell
uv run python src/scripts/crawl_quality_report.py --crawl-run-id <run_id>
```

Focus on:

- `current_usable_raw_count`
- `blocked_count`
- `failed_count`
- `CRAWL_SKIPPED`
- `source_seed_health`
- `refreshed_raw_count`
- `first_seen_at`
- `last_crawled_at`

## MVP Shipping Bar

For release readiness, use the 4-field usability check:

- title
- company
- description
- requirements

The 5-section TopCV metrics remain quality diagnostics and help catch extraction regressions, but they are not the MVP blocker.
The default run pipeline skips LLM validity validation so the MVP path can move forward without extra rate-limit risk.

For the processor-side contract and field ownership split, see [Job Processor Contract](./processor_contract.md).

## What Not To Infer From Global Rows

- Do not use global historical audit counts to judge the current run.
- Do not assume `raw_to_clean_pct` alone describes current crawl quality.
- Existing clean jobs may come from older successful runs and can make blocked rows look more misleading than they are.
- Prefer run-scoped raw jobs and run-scoped audits when deciding the next crawler change.

## Current Recommended Experiment

```powershell
uv run python src/run_pipeline.py --limit 1 --force-recrawl --crawl-only
uv run python src/scripts/crawl_quality_report.py --crawl-run-id <run_id>
```

This keeps the crawl isolated, avoids LLM noise, and makes the report easy to compare across controlled TopCV experiments.
