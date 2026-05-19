# Run Scraper

Current scraper entry points:

```bash
uv run python src/run_pipeline.py --limit 10
```

If you need the crawler internals directly, import the canonical flow instead of a deleted CLI:

```python
from src.internhunter.orchestration.ingestion_flow import job_ingestion_flow
```

## Notes

- The scraper discovers links first, then crawls detail pages through the orchestration flow.
- It stores raw job rows and audit failures.
