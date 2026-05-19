# Deployment

## Current Paths

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
- Scripted runtime entrypoints live under `src/run_pipeline.py`, `src/internhunter/orchestration/`, and `src/scripts/`.

## Notes

- The current supported runtime path is `src/run_pipeline.py`; keep Docker commands aligned with that entrypoint.
