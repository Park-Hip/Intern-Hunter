# Testing

## Test Categories

### Unit

- pure mapping and validation logic
- repository helpers with mocked database sessions
- parser and formatter behavior

### Integration

- Prefect flow execution with mocked crawler and LLMs
- database writes across the ETL chain

### Fixture-Based Scraper Tests

- page fixtures that simulate TopCV structures
- extractor behavior on known HTML or markdown samples

### Database Tests

- raw job insert and dedupe
- parsed job writes
- telemetry writes
- resume profile storage behavior

### Search and Matching Tests

- structured filters
- vector similarity ranking
- resume upload and match flow

## Current Test Files

- `tests/unit/test_job_processor.py`
- `tests/unit/test_etl_repository.py`
- `tests/integration/test_ingestion_flow.py`

## Notes

- Tests currently rely on heavy mocking.
- TODO: add real fixture coverage for extraction and search ranking.
