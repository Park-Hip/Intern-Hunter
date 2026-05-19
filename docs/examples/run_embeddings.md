# Run Embeddings

The embedding path runs through the processing command:

```bash
uv run python src/run_pipeline.py --limit 10
```

## Notes

- Embeddings are created during job processing, not as a standalone public API.
- The old `src/scripts/backfill_embeddings.py` maintenance helper has been removed.
- `src/main.py` is no longer part of the supported command surface.
