# Troubleshooting

## TopCV Page Structure Changed

Symptoms:
- CSS extraction suddenly returns missing fields
- many jobs fall back to raw markdown

Checks:
- inspect the extracted page JSON
- compare the current selectors in `src/internhunter/crawler/crawl_config.py`
- verify whether the page still exposes the same job detail structure

## Crawler Blocked

Symptoms:
- captcha or verification page appears
- `audit_jobs.error_type = BOT_DETECTED`
- screenshot files appear in `errors/`

Checks:
- confirm the block page text
- check delays and retry settings
- verify browser automation is still launching correctly

## Database Connection Failed

Symptoms:
- repository calls fail
- table creation or inserts do not complete

Checks:
- confirm `DB_URL`
- confirm PostgreSQL is running
- confirm `pgvector` is installed

## Embedding Provider Failed

Symptoms:
- job parse succeeds but embedding is missing

Checks:
- confirm Gemini credentials
- check translation fallback behavior
- inspect provider logs for rate limits or API failures

## Prefect Flow Failed

Symptoms:
- task retries exhaust
- pipeline summary is incomplete

Checks:
- inspect task logs
- verify the active flow entry point
- confirm the database tables exist before the flow starts

## Resume Parsing Failed

Symptoms:
- user profile exists but matching cannot run
- resume embedding is missing

Checks:
- confirm the resume text was stored
- confirm the embedding step succeeded
- verify the resume upload path and the `user_profiles` row
