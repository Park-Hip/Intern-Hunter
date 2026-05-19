# Monitoring

## Current Signals

- structlog output from the application
- `pipeline_runs` rows for ETL summaries
- `audit_jobs` rows for failures
- MLflow configuration in `src/config/settings.yaml`

## What to Watch

- crawler block rates
- validation failures
- provider fallback frequency
- embedding failures
- database write errors
- Prefect task failures

## Notes

- Monitoring is still mostly log-and-table based.
- TODO: verify whether any external dashboards or alerts are configured elsewhere.
