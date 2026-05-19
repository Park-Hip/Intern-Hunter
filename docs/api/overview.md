# API Overview

## Current Endpoints

- `GET /` -> returns a short API banner message
- `GET /health` -> returns a health check response
- `GET /jobs/search` -> returns criteria-based or semantic job search results
- `POST /resume/match` -> uploads resume text, stores the embedding, and returns matched jobs

## Request Shapes

`GET /jobs/search` query parameters:

- `query: str` with default `"data scientist"`
- `limit: int` with default `5`
- `mode: str` with supported values `criteria` and `semantic`

`POST /resume/match` request body:

- `user_id: str`
- `resume_text: str`
- `limit: int = 5`

The only explicit public request model defined in code is `ResumeMatchRequest` in `src/internhunter/api/routes/demo_routes.py`.

## Response Shapes

- `GET /` returns `{"message": "InternHunter MVP API"}`
- `GET /health` returns a status object with `status`, `db`, and `search`
- `GET /jobs/search` returns `list[dict]`
- `POST /resume/match` returns `list[dict]`

Search and match result rows are repository-backed dictionaries, not dedicated HTTP DTO classes.

## Current Error Behavior

- `GET /health` returns a degraded status payload when the DB check fails instead of raising an HTTP error.
- `GET /jobs/search` returns `400` when `mode` is not `criteria` or `semantic`.
- `GET /jobs/search` returns `500` when embedding generation or repository search fails.
- `POST /resume/match` returns `400` when `resume_text` is empty after trimming.
- `POST /resume/match` returns `404` when no resume can be matched or no jobs are found.
- `POST /resume/match` returns `500` when upload, embedding, or matching fails.

## Data-Layer Failure Types

These appear in `audit_jobs.error_type`:

- `BOT_DETECTED`
- `CRAWL_FAILED`
- `VALIDATION_FAILED`
- `LLM_INCOMPLETE`
- `PROCESSING_ERROR`

## Notes

- The API surface now centers on search and resume matching.
- Keep this page aligned with `src/internhunter/api/routes/demo_routes.py`.
- The live API is mostly untyped at the HTTP boundary apart from `ResumeMatchRequest`.
