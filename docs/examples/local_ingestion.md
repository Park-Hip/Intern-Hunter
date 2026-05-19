# Local Ingestion

This is the shortest path to run the current ETL locally.

```bash
docker-compose up -d
uv run python src/scripts/upgrade_db.py
uv run python src/run_pipeline.py --limit 10
```

## Notes

- This assumes `.env` is already set.
- The run will use the crawler, validation, extraction, embedding, and database layers together.
