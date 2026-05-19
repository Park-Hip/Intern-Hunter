# Setup

## Prerequisites

- Python 3.12+
- `uv`
- PostgreSQL with `pgvector`
- Docker and Docker Compose if you want the bundled database container

## Environment

Create a `.env` file in the project root. The current code reads:

- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `DB_URL`
- optional legacy seed URLs `DS_URL` and `AIE_URL`

The repository also uses YAML config files:

- `src/config/settings.yaml`
- `src/config/prompts.yaml`

## Common Commands

```bash
uv sync
docker-compose up -d
uv run python src/scripts/upgrade_db.py
uv run python src/run_pipeline.py --limit 10
uv run uvicorn src.internhunter.api.app:app --reload
```

## Notes

- `docker-compose.yml` starts PostgreSQL with `pgvector`.
- `src/scripts/upgrade_db.py` is a lightweight table-verification helper.
- The project now assumes the active database schema is current.
- `src/main.py` is intentionally removed; use `src/run_pipeline.py`, `src/internhunter/orchestration/ingestion_flow.py`, or scripts under `src/scripts/` instead.
