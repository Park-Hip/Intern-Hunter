# API Overview

## Current Endpoints

- `GET /` -> returns a short API banner message
- `GET /health` -> returns a health check response
- `GET /jobs/search` -> returns criteria-based or semantic job search results
- `POST /resume/match` -> uploads resume text, stores the embedding, and returns matched jobs
- `POST /agent/ask` -> accepts the database-agent request envelope and currently returns bounded refusal, preview, or a generic allowed placeholder response

## Request Shapes

`GET /jobs/search` query parameters:

- `query: str` with default `"data scientist"`
- `limit: int` with default `5`
- `mode: str` with supported values `criteria` and `semantic`

`POST /resume/match` request body:

- `user_id: str`
- `resume_text: str`
- `limit: int = 5`

`POST /agent/ask` request body (`AgentAskRequest` in `src/internhunter/api/schemas/agent.py`):

- `question: str`
- `session_id: str | null = null`
- `user_id: str | null = null`
- `preview_only: bool = false`
- `include_chart: bool = false`
- `limit: int | null = null`
- `include_summary: bool = true`
- `debug: bool = false`

The explicit public request models currently defined in code are `ResumeMatchRequest` in `src/internhunter/api/routes/demo_routes.py` and `AgentAskRequest` in `src/internhunter/api/schemas/agent.py`.

## Response Shapes

- `GET /` returns `{"message": "InternHunter MVP API"}`
- `GET /health` returns a status object with `status`, `db`, and `search`
- `GET /jobs/search` returns `list[dict]`
- `POST /resume/match` returns `list[dict]`
- `POST /agent/ask` returns a typed shared envelope with top-level `status`, `question`, `sql`, `table`, `summary`, `chart`, `warnings`, `metadata`, and `error`

Search and match result rows are repository-backed dictionaries, not dedicated HTTP DTO classes.

The current `/agent/ask` implementation is intentionally narrow:

- blocked unsafe or out-of-scope requests return a typed `status="refused"` envelope before branch execution
- allowed prompts return one generic scaffolded `status="ok"` placeholder response
- `preview_only=true` still returns a preview-shaped `status="ok"` envelope with stub `validated_sql`
- no live path generates SQL, executes SQL, performs resume matching, or produces charts yet

## Current Error Behavior

- `GET /health` returns a degraded status payload when the DB check fails instead of raising an HTTP error.
- `GET /jobs/search` returns `400` when `mode` is not `criteria` or `semantic`.
- `GET /jobs/search` returns `500` when embedding generation or repository search fails.
- `POST /resume/match` returns `400` when `resume_text` is empty after trimming.
- `POST /resume/match` returns `404` when no resume can be matched or no jobs are found.
- `POST /resume/match` returns `500` when upload, embedding, or matching fails.
- `POST /agent/ask` returns `422` for malformed payloads under the current FastAPI/Pydantic validation path.
- `POST /agent/ask` currently returns `200` for bounded `ok`, preview, and refusal responses.

## Data-Layer Failure Types

These appear in `audit_jobs.error_type`:

- `BOT_DETECTED`
- `CRAWL_FAILED`
- `VALIDATION_FAILED`
- `LLM_INCOMPLETE`
- `PROCESSING_ERROR`

## Notes

- The API surface now centers on search and resume matching.
- `POST /agent/ask` is now part of the live API surface, with deterministic pre-agent screening and bounded placeholder handling, but it is still a scaffolded boundary rather than a real SQL-capable agent.
- Keep this page aligned with `src/internhunter/api/routes/demo_routes.py`, `src/internhunter/api/routes/agent_routes.py`, and `src/internhunter/api/schemas/agent.py`.
- The live API is still lightly typed at the HTTP boundary outside the `/agent/ask` scaffold.
