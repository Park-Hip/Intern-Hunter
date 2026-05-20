# InternHunter MVP Backend

InternHunter is a TopCV-focused job-finder backend that crawls jobs, stores raw and cleaned job data, generates embeddings, and supports DB search, semantic search, and resume matching.

## Current MVP Backend Capabilities

- TopCV crawl -> `raw_jobs`
- `raw_jobs.crawl_run_id` stamps each crawl snapshot with the current run
- `raw_jobs` -> `clean_jobs`
- `clean_jobs` -> embeddings
- DB-only search
- semantic search
- resume upload -> embedding
- resume matching -> jobs
- resume match explanations
- bounded `/agent/ask` guardrail scaffold
- minimal local API demo

## Quickstart

### 1. Set up the environment

Make sure PostgreSQL is running and set:

- `DB_URL`
- Gemini API key for embeddings and resume matching

If your local database is missing the latest columns, run:

```powershell
uv run python src/scripts/upgrade_db.py
```

### 2. Run a small ETL slice

```powershell
uv run python src/run_pipeline.py --limit 3 --force-recrawl --skip-llm-validation
```

### 3. Run semantic search smoke

```powershell
uv run python src/scripts/semantic_search_smoke.py
```

Optional query override:

```powershell
uv run python src/scripts/semantic_search_smoke.py --query "python machine learning internship"
```

### 4. Start the API demo

```powershell
uv run uvicorn src.internhunter.api.app:app --reload
```

### 5. Run the API smoke script

Start the API first, then run:

```powershell
uv run python src/scripts/api_demo_smoke.py
```

If you are missing a Gemini key, hit quota, or want to demo the DB-only backend path, use:

```powershell
uv run python src/scripts/api_demo_smoke.py --skip-semantic --skip-resume
```

The script checks:

- `/health`
- `/jobs/search` in criteria mode
- `/jobs/search` in semantic mode unless skipped
- `/resume/match` unless skipped

## API Endpoints

- `GET /health`
- `GET /jobs/search` (`mode=criteria` by default, `mode=semantic` available when the Gemini embedding key is configured)
- `POST /resume/match` returns matched jobs plus `matched_skills`, `unmatched_resume_skills`, and `reason`
- `POST /agent/ask` returns a typed database-agent envelope with deterministic refusal, preview, and generic allowed placeholder behavior

Examples:

```powershell
curl http://127.0.0.1:8000/health
curl "http://127.0.0.1:8000/jobs/search?query=data%20scientist&limit=5"
curl "http://127.0.0.1:8000/jobs/search?query=python%20machine%20learning&limit=5&mode=semantic"
curl -X POST http://127.0.0.1:8000/resume/match `
  -H "Content-Type: application/json" `
  -d "{\"user_id\":\"demo-user\",\"resume_text\":\"Python data scientist with machine learning, SQL, NLP, statistics, FastAPI, and data visualization experience.\",\"limit\":5}"
```

`POST /resume/match` also adds deterministic rule-based explanations:

- `matched_skills`
- `unmatched_resume_skills`
- `reason`

`unmatched_resume_skills` means resume skills that were not explicitly found in the returned job text. It does **not** mean the candidate lacks those skills.

## Documentation

- [Docs index](docs/README.md)
- [Setup](docs/getting-started/setup.md)
- [Current behavior](docs/current-system/current_behavior.md)
- [API overview](docs/api/overview.md)
- [Agent planning docs](docs/agent/vision.md)

## Known Limitations

- TopCV may block crawling with Cloudflare.
- Gemini key/quota is still needed for embeddings and resume matching.
- `match_score` is meaningful in semantic mode, but criteria mode still uses exact/fallback behavior.
- No auth yet.
- No frontend yet.
- Semantic `/jobs/search` depends on the Gemini key/quota.
- Resume match explanations are curated and conservative, so they may miss synonyms or Vietnamese phrasing.
