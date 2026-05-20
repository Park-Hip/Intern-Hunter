# Current Behavior

This file describes what the code does today, not what it should do later.

## What Works Today

- TopCV job links are discovered from the configured search URLs in `src/internhunter/config/settings.py`.
- The crawler paginates search results and normalizes job URLs before saving.
- Detail extraction uses a CSS-first path and falls back to raw markdown when CSS extraction looks weak.
- Raw jobs are stored in PostgreSQL as staging rows.
- Validation runs before LLM parsing.
- LLM parsing uses Gemini first and Groq as fallback.
- Embeddings are generated at 768 dimensions.
- Structured jobs are stored in `clean_jobs`.
- Failures are recorded in `audit_jobs`.
- Pipeline runs are summarized in `pipeline_runs`.
- Resume profile data is stored in `user_profiles`.
- The current codebase assumes the active database schema is already up to date.

These statements are based on the current repository structure, ORM models, scripts, and API routes.

## Working Paths

The following backend slices are working end to end in the local environment:

1. TopCV crawl -> `raw_jobs`
2. `raw_jobs.crawl_run_id` stamps each crawl snapshot with the current run
3. `raw_jobs` -> `clean_jobs`
4. `clean_jobs` -> embeddings
5. DB-only search
6. Semantic search
7. Resume upload -> embedding
8. Resume matching -> jobs
9. Resume match explanations
10. API demo

## Available Endpoints

1. `GET /health`
2. `GET /jobs/search`
3. `POST /resume/match`
4. `POST /agent/ask` (guardrail + runtime-backed allowed path + preview stub for the database-agent phase)

See [API Overview](../api/overview.md) for the live API surface.

## Runtime Entry Points

- API app: `src/internhunter/api/app.py`
- Pipeline CLI wrapper: `src/run_pipeline.py`
- Prefect orchestration: `src/internhunter/orchestration/`
- Smoke and maintenance scripts: `src/scripts/`

## Configuration Behavior

- Normal runtime defaults now come from `src/config/settings.yaml`.
- `.env` is used for secrets and deployment-specific overrides such as `DB_URL`, provider keys, Langfuse credentials, environment name, and optional MLflow overrides.
- `crawler.topcv.search_seeds` is the only default source for crawler search URLs.

## Known Modules and Files

- `src/internhunter/config/settings.py`
- `src/config/settings.yaml`
- `src/config/prompts.yaml`
- `src/internhunter/api/app.py`
- `src/internhunter/api/routes/demo_routes.py`
- `src/internhunter/api/routes/agent_routes.py`
- `src/internhunter/api/schemas/agent.py`
- `src/agents/service.py`
- `src/internhunter/orchestration/ingestion_flow.py`
- `src/run_pipeline.py`
- `src/internhunter/crawler/crawl.py`
- `src/internhunter/crawler/crawl_config.py`
- `src/internhunter/extraction/job_processor.py`
- `src/internhunter/extraction/validator.py`
- `src/internhunter/embeddings/embedder.py`
- `src/internhunter/storage/models.py`
- `src/internhunter/storage/session.py`
- `src/internhunter/storage/repositories/etl.py`
- `src/internhunter/search/repository.py`
- `src/internhunter/llm/router.py`
- `src/internhunter/llm/providers.py`
- `src/internhunter/resume/matching.py`
- `src/internhunter/resume/repository.py`
- `tests/unit/test_job_processor.py`
- `tests/unit/test_etl_repository.py`
- `tests/integration/test_ingestion_flow.py`

## Known Problems

- The canonical ingestion entry point is `src/internhunter/orchestration/ingestion_flow.py`, with `src/run_pipeline.py` as the supported CLI wrapper.
- Search and resume matching exist as dedicated repository-backed code and are exposed through the demo API endpoints.
- `POST /agent/ask` now performs deterministic pre-agent screening, keeps the preview stub path, and routes other allowed requests through the Milestone 1 runtime foundation. The live request contract is minimal (`question`, optional `session_id`, optional `user_id`, optional `preview_only`), query-limit policy remains internal agent configuration, short in-process session memory is wired through `session_id`, and tracing now has a real seam with Langfuse-backed tracing when configured and fail-open tracing otherwise. The current default allowed-path runtime depends on a responsive local Ollama provider. Real SQL generation, validation, execution, charting, and live resume-tool routing are still not implemented.
- Test coverage is present, but much of it is still narrow and heavily mocked.

## Required Environment

Minimum required environment:

1. `DB_URL`
2. Gemini API key for embeddings

Still needed in some paths:

1. Groq/Gemini for LLM validation and extraction when LLM validation is enabled
2. Gemini API key for the `/resume/match` demo endpoint

## Known Limitations

The MVP backend works, but the following limitations are still known:

1. TopCV Cloudflare blocking still happens on live crawls.
2. CSS extraction often falls back to raw fallback.
3. `match_score` is meaningful in semantic search, but criteria mode still uses exact/fallback behavior.
4. `--force-recrawl` is dev-only and should not be treated as a production mode.
5. `--skip-llm-validation` is dev-only and should not be treated as a production mode.
6. There is no UI yet.
7. There is no polished API demo yet.
8. `/jobs/search` supports both criteria and semantic modes; semantic mode depends on the Gemini embedding key/quota.
9. `/resume/match` needs a Gemini embedding key.
10. There is no auth.
11. This is not full raw-job versioning; the same URL still maps to one refreshed raw row.
12. Older raw rows may still have `crawl_run_id = NULL`.
13. Global processing can still run without `crawl_run_id` when you want legacy backlog behavior.
14. Resume match explanations are curated and conservative; they can miss synonyms or Vietnamese phrasing.
15. Ranking still comes from embeddings; explanations are added after the semantic results are returned.
16. `/agent/ask` can now return guardrail refusals, preview-stub responses, or runtime-backed allowed `ok` responses with reusable short session memory keyed by `session_id`, but it still does not perform real SQL generation/execution, chart generation, or real resume-tool execution. SQL/table/summary/chart fields remain optional response artifacts, not request-selected outputs.

## Verification Commands

### Unit tests

```powershell
uv run pytest tests/unit -q
```

### ETL smoke

```powershell
uv run python src/run_pipeline.py --limit 3 --force-recrawl --skip-llm-validation
```

### Search smoke

```powershell
uv run python src/scripts/semantic_search_smoke.py
```

### Resume smoke

```powershell
uv run python -c "from src.internhunter.resume import execute_upload_resume, execute_match_resume; user_id='smoke-user'; resume='Python data scientist with machine learning, SQL, NLP, statistics, FastAPI, and data visualization experience.'; print(execute_upload_resume(user_id, resume)); print(execute_match_resume(user_id, limit=5))"
```

### API demo smoke

```powershell
uv run uvicorn src.internhunter.api.app:app --reload
```

## Must Not Break

- URL deduplication before saving raw jobs.
- CSS-first extraction with raw fallback.
- Blocked-page audit handling and screenshot capture.
- Validation before LLM parsing.
- Gemini -> Groq fallback behavior.
- 768-dimension embedding generation.
- `raw_jobs.status` transitions to `completed` or `failed`.
- `pipeline_runs` telemetry writes.
