# Setup

## Prerequisites

- Python 3.12+
- `uv`
- PostgreSQL with `pgvector`
- Docker and Docker Compose if you want the bundled database container

## Environment

Create a `.env` file in the project root. The current code reads:

- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `DB_URL`
- optional deployment overrides such as `ENVIRONMENT`
- optional monitoring/tracing overrides such as `MLFLOW_TRACKING_URI`, `MLFLOW_EXPERIMENT`, and `LANGFUSE_*`

The repository also uses YAML config files:

- `src/config/settings.yaml`
- `src/config/prompts.yaml`

## Common Commands

```bash
uv sync
docker-compose up -d
uv run python src/scripts/upgrade_db.py
uv run python src/run_pipeline.py --limit 10
uv run uvicorn src.internhunter.api.app:app --reload
```

## Notes

- `docker-compose.yml` starts PostgreSQL with `pgvector`.
- `src/config/settings.yaml` is the default-value source for app, agent, crawler, llm, logging, and mlflow settings.
- `.env` should be treated primarily as the home for secrets and deployment-specific overrides.
- The current default `/agent/ask` provider path expects a reachable local Ollama server at the configured `agent.provider.base_url` with the configured model already available.
- Agent tracing uses Langfuse's official LangChain `CallbackHandler` for runtime calls. The pre-agent guardrail is traced separately as one Langfuse observation because it runs outside LangChain. If Langfuse is unavailable, the API still returns a local `trace_id` and fails open.
- `src/scripts/upgrade_db.py` is a lightweight table-verification helper.
- The project now assumes the active database schema is current.
- There is no `src/main.py` entrypoint in this repo. Use `src/run_pipeline.py` for pipeline work, `uvicorn src.internhunter.api.app:app --reload` for local API work, and `src/scripts/` for targeted smoke or maintenance flows.
