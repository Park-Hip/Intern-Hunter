# Prefect

## Current Use

- `src/internhunter/orchestration/ingestion_flow.py` defines the main ingestion flow.
- `src/run_pipeline.py` is the supported CLI entrypoint for local execution.

## What Prefect Handles

- retries
- task boundaries
- flow-level orchestration
- pipeline run telemetry

## Notes

- `src/internhunter/orchestration/ingestion_flow.py` is the canonical flow module.
- Keep orchestration changes separate from crawler and processor changes.
