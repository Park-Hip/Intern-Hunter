# InternHunter Docs

InternHunter is an automated job discovery and resume-matching platform for TopCV listings.

This docs set is meant to support safe refactoring:
- it describes the code as it exists now
- it separates implemented behavior from planned work
- it keeps module boundaries and data contracts explicit

## Read This First

1. [setup](./getting-started/setup.md) for local environment and common commands
2. [current behavior](./current-system/current_behavior.md) for what works today
3. [architecture overview](./architecture/overview.md) for the high-level code layout
4. [agent docs](./agent/vision.md) if you are working on the database-agent phase

## Getting Started

- [getting-started/setup.md](./getting-started/setup.md): local setup and common commands

## Current System

- [current-system/current_behavior.md](./current-system/current_behavior.md): implemented behavior, limits, and verification commands
- [current-system/etl_crawler_semantics.md](./current-system/etl_crawler_semantics.md): crawler and ETL semantics that describe current pipeline behavior
- [current-system/processor_contract.md](./current-system/processor_contract.md): current processor boundaries and field ownership

## Architecture

- [architecture/overview.md](./architecture/overview.md): high-level system structure
- [architecture/module_boundaries.md](./architecture/module_boundaries.md): ownership by package and subsystem
- [architecture/etl_pipeline.md](./architecture/etl_pipeline.md): ETL flow and checkpoints
- [architecture/database_schema.md](./architecture/database_schema.md): current schema summary
- [architecture/data_contracts.md](./architecture/data_contracts.md): current model and contract notes
- [architecture/search_architecture.md](./architecture/search_architecture.md): current search design
- [architecture/resume_matching.md](./architecture/resume_matching.md): current resume-matching flow

## Operations

- [operations/configuration.md](./operations/configuration.md): runtime configuration sources and settings
- [operations/prefect.md](./operations/prefect.md): current Prefect usage
- [operations/deployment.md](./operations/deployment.md): current deployment paths
- [operations/monitoring.md](./operations/monitoring.md): current signals and watchpoints
- [operations/troubleshooting.md](./operations/troubleshooting.md): common operational failures

## Development

- [development/testing.md](./development/testing.md): current test categories and gaps
- [development/code_style.md](./development/code_style.md): style expectations for safe refactors
- [development/logging.md](./development/logging.md): current logging rules
- [development/ai_workflow.md](./development/ai_workflow.md): contributor workflow and AI-assisted change guardrails

## API

- [api/overview.md](./api/overview.md): current endpoints, models, and error behavior

## Agent

- [agent/vision.md](./agent/vision.md): product direction for the future SQL-first, bounded multi-tool database agent
- [agent/database_agent_mvp_roadmap.md](./agent/database_agent_mvp_roadmap.md): phased execution roadmap from current state to the bounded multi-tool SQL-first MVP
- [agent/architecture.md](./agent/architecture.md): planned runtime boundaries for the agent layer
- [agent/sql_contract.md](./agent/sql_contract.md): future SQL safety and generation contract
- [agent/data_dictionary.md](./agent/data_dictionary.md): query-facing interpretation of `clean_jobs`
- [agent/eval_set.md](./agent/eval_set.md): planned evaluation cases
- [agent/api_contract.md](./agent/api_contract.md): planned agent API surface
- [agent/security_model.md](./agent/security_model.md): planned agent security model

## Examples

- [examples/local_ingestion.md](./examples/local_ingestion.md)
- [examples/run_scraper.md](./examples/run_scraper.md)
- [examples/run_embeddings.md](./examples/run_embeddings.md)
- [examples/search_examples.md](./examples/search_examples.md)
