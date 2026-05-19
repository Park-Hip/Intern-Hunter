# Deployment

## Current Paths

- API app in `src/internhunter/api/app.py`
- Pipeline wrapper in `src/run_pipeline.py`
- Canonical Prefect flows in `src/internhunter/orchestration/`
- Maintenance scripts under `src/scripts/` when still used
- Local database container support via `docker-compose.yml`
- Supporting deployment script in `deployment.py`

## Removed Path

- `src/main.py` was intentionally removed as a user-facing CLI entry point.

## Current Deployment Shape

- PostgreSQL runs in a container with `pgvector`.
- Local API and pipeline commands are run from the Python project environment.
- Scripted runtime entrypoints live under `src/internhunter/api/app.py`, `src/run_pipeline.py`, `src/internhunter/orchestration/`, and `src/scripts/`.

## Notes

- For local API work, use `uv run uvicorn src.internhunter.api.app:app --reload`.
- For ETL and ingestion work, use `src/run_pipeline.py` or the orchestration flows under `src/internhunter/orchestration/`.
