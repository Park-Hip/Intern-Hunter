# Configuration

## Current Sources

- Runtime defaults are loaded from `src/config/settings.yaml`.
- Environment variables from `.env` are used for secrets and deployment-specific overrides.
- Prompt templates are read from `src/config/prompts.yaml`.

## Main Settings

- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `DB_URL`
- `POSTGRES_PASSWORD`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST`
- `ENVIRONMENT`
- `MLFLOW_TRACKING_URI`
- `MLFLOW_EXPERIMENT`
- `app.*`
- `agent.*`
- `crawler.*`
- `llm.*`
- `logging.*`
- `mlflow.*`

## Notes

- The code uses `pydantic-settings`.
- `src/config/settings.yaml` is the single source of truth for normal defaults under `app`, `agent`, `crawler`, `llm`, `logging`, and `mlflow`.
- `crawler.topcv.search_seeds` is the only default source for TopCV search URLs.
- Runtime consumers should use typed settings sections such as `settings.llm`, `settings.logging`, and `settings.mlflow` instead of raw YAML dictionary lookups.
- `src/config/prompts.yaml` is the centralized catalog for LLM prompts, including extraction, translation, and validation prompts.
