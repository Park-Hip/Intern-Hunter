# Docs Audit Note (2026-05-19)

This note records the source-of-truth checks used for the baseline docs cleanup in the current `job_finder` repo.

## Source Of Truth Inventory

- Canonical API entrypoint: `uv run uvicorn src.internhunter.api.app:app --reload`
- Pipeline CLI entrypoint: `uv run python src/run_pipeline.py --limit 10`
- Current smoke scripts:
  - `src/scripts/api_demo_smoke.py`
  - `src/scripts/semantic_search_smoke.py`
- Current public endpoints:
  - `GET /`
  - `GET /health`
  - `GET /jobs/search`
  - `POST /resume/match`
  - `POST /agent/ask`
- Current database-agent implementation status:
  - typed request/response models exist
  - route wiring exists
  - thin stub orchestration exists
  - real SQL/query routing, validation, execution, memory, charting, and resume-tool routing are not implemented yet

## Audit Findings

| File | Classification | Issue | Planned Action |
| --- | --- | --- | --- |
| `README.md` | fixable drift | API docs omitted the live `/agent/ask` stub and its limitations. | Add the endpoint and describe current stub status. |
| `docs/README.md` | fixable drift | Agent/development navigation needed clearer wording for the live scaffold versus planning docs. | Tighten descriptions and add this audit note. |
| `docs/getting-started/setup.md` | fixable drift | Setup notes over-emphasized removed entrypoints instead of the current API entrypoint. | Point to the actual API and pipeline commands. |
| `docs/current-system/current_behavior.md` | fixable drift | Current endpoints omitted `/agent/ask`, and runtime notes were still framed around `src/main.py`. | Rewrite runtime entrypoints around current code paths and note the stub endpoint. |
| `docs/api/overview.md` | fixable drift | Live API overview omitted `/agent/ask` and its typed model boundary. | Add the endpoint, request/response shapes, and current `422` validation behavior. |
| `docs/agent/api_contract.md` | fixable drift | Status said “planning only” even though the route and models exist. | Mark the current implemented slice while keeping the rest of the document as target MVP behavior. |
| `docs/agent/architecture.md` | fixable drift | Status implied no runtime scaffold existed yet. | Note the current thin route and service seam. |
| `docs/operations/deployment.md` | fixable drift | Deployment notes over-centered `src/run_pipeline.py` and under-described the real API entrypoint. | Add the API runtime path and rebalance the notes. |
| `docs/development/testing.md` | fixable drift | Test inventory no longer matched the current repo. | Refresh the current test files and agent scaffold coverage notes. |
| `docs/examples/run_embeddings.md` | current with minor drift | The command is still valid, but the note about `src/main.py` is no longer the clearest guidance. | Simplify the note. |
| `docs/architecture/overview.md` | current | High-level package map is still accurate. | Keep as-is apart from small layout clarification if needed. |

## Archive Decisions

- No docs were archived in this pass.
- The drift found here was narrow enough to fix in place without introducing a new archive folder.
