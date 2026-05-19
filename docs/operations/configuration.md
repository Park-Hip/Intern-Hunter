# Configuration

## Current Sources

- Environment variables are loaded from `.env` by `src/internhunter/config/settings.py`.
- Runtime defaults and overrides are read from `src/config/settings.yaml`.
- Prompt templates are read from `src/config/prompts.yaml`.

## Main Settings

- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `DB_URL`
- `DS_URL`
- `AIE_URL`
- `crawler.*`
- `llm.*`
- `logging.*`
- `mlflow.*`

## Notes

- The code uses `pydantic-settings`.
- `src/config/prompts.yaml` is the centralized catalog for LLM prompts, including extraction, translation, and validation prompts.
- `src/config/settings.yaml` currently defines `llm.*`, `agent.*`, `crawler.*`, `logging.*`, and `mlflow.*` sections.
