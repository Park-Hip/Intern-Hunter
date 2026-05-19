# ETL Pipeline

## Intended Flow

1. TopCV listing pages are crawled.
2. Job detail pages are fetched from the discovered URLs.
3. Raw results are stored in `raw_jobs`.
4. Raw content is validated.
5. CSS extraction is attempted first.
6. Raw markdown fallback is used when CSS extraction is weak.
7. Valid raw jobs are transformed into structured jobs.
8. Structured jobs are embedded.
9. Clean jobs are written to `clean_jobs`.
10. Failures are routed to `audit_jobs`.
11. Run summaries are written to `pipeline_runs`.

## Important Rules

- Deduplicate URLs before saving.
- Keep blocked-page handling separate from generic crawl failure.
- Preserve raw data so refactoring can replay or reprocess it later.
- Do not skip validation just because extraction succeeded.
