# Logging

## Current Setup

- Logging is configured through `src/internhunter/common/logging.py`.
- structlog context binding is used for run IDs and phase labels.
- The output format is driven by `src/config/settings.yaml`.

## Rules

- Log structure should stay stable across refactors.
- Prefer key-value logs over free-form strings.
- Include run IDs for ingestion and processing steps.

## Notes

- `pipeline_runs` and `audit_jobs` should be treated as the durable record of failures and summaries.
