# Monitoring

## Current Signals

- structlog output from the application
- `pipeline_runs` rows for ETL summaries
- `audit_jobs` rows for failures
- typed MLflow defaults from `src/config/settings.yaml`
- optional Langfuse v3 tracing credentials and host from `.env`

## What to Watch

- crawler block rates
- validation failures
- provider fallback frequency
- embedding failures
- database write errors
- Prefect task failures

## Notes

- Monitoring is still mostly log-and-table based.
- With Langfuse configured, `/agent/ask` traces the allowed runtime path through LangChain's callback integration and records the pre-agent guardrail as one separate observation.
- TODO: verify whether any external dashboards or alerts are configured elsewhere.
