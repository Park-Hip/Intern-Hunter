# Architecture Overview

InternHunter is currently organized like a modular monolith:

- orchestration lives in Prefect flows and CLI entry points
- business logic lives in services
- external integrations live in infrastructure modules
- shared types live in `src/core`

## Main Flow

TopCV listing pages -> job detail pages -> raw storage -> validation -> LLM extraction -> clean jobs -> embeddings -> search and matching

## Main Layers

- `src/internhunter/config/` for settings and prompts
- `src/core/` for shared models and utilities
- `src/internhunter/crawler/` for crawling and extraction
- `src/internhunter/extraction/` for processing and validation
- `src/internhunter/storage/` for ORM and repositories
- `src/internhunter/llm/` for provider/router logic
- `src/internhunter/orchestration/` for pipeline orchestration
- `src/internhunter/search/` and `src/internhunter/resume/` for retrieval and matching
- `src/internhunter/api/` for public endpoints
- `src/agents/` for the early database-agent service and shared internal agent types

Future database-agent planning lives under `docs/agent/`.
