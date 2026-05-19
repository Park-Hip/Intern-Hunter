# AGENTS.md

## Active phase

The current active phase is the **Database Agent Layer**.

The ETL/crawler phase is frozen for MVP unless a true blocking bug appears.

The new goal is to build an agent system that can:
- turn English questions into safe SQL
- execute read-only SQL against the existing job-finder database
- return tables
- generate chart/graph specs
- help users explore the job database

## Current project status

The backend already has:
- ETL/crawler pipeline
- `raw_jobs`
- `clean_jobs`
- structured `full_json_dump`
- processor contract
- search API
- resume matching API
- LLM provider infrastructure
- FastAPI app

Do not restart crawler/ETL design unless explicitly requested.

## Before starting any task

Read the relevant docs first:

If a document is still a placeholder, do not invent large decisions silently. Propose the missing decision first.

## Frozen areas

Do not modify these unless the user explicitly asks:

- crawler extraction logic
- TopCV selectors
- proxy settings
- crawl pacing / blocking strategy
- `raw_jobs` / `clean_jobs` schema
- JobProcessor contract
- LLM validation behavior
- existing search API
- existing resume matching API
- ETL orchestration

If a task seems to require touching a frozen area, explain why before changing it.

## Agent layer scope

The database agent layer may add code under new modules such as:

- `src/agents/`
- `src/services/query/`
- `src/internhunter/api/routers/agent.py`
- `tests/unit/test_sql_safety.py`
- `tests/unit/test_schema_inspector.py`
- `tests/integration/test_agent_api.py`

Prefer adding new isolated modules over modifying stable ETL code.

## SQL safety rules

All agent-generated SQL must be validated before execution.

Allowed:
- `SELECT`
- aggregate functions
- `GROUP BY`
- `ORDER BY`
- `LIMIT`

Blocked:
- `INSERT`
- `UPDATE`
- `DELETE`
- `DROP`
- `ALTER`
- `CREATE`
- `TRUNCATE`
- `REPLACE`
- `MERGE`
- `COPY`
- `ATTACH`
- `DETACH`
- `PRAGMA`
- `VACUUM`
- `GRANT`
- `REVOKE`
- multiple SQL statements
- `WITH` / CTE queries for MVP
- joins for MVP

Use a table and column whitelist.

Start with plain single-table `clean_jobs` queries only unless the user expands the allowed schema.

Always apply a safe default `LIMIT` if the query does not include one.

Never execute SQL that fails safety validation.

## Testing expectations

For every behavior change:
- add or update focused tests
- run the smallest relevant test set
- report exact commands and results

For SQL safety work, always test:
- safe `SELECT` allowed
- write/admin SQL rejected
- multi-statement SQL rejected
- unknown table rejected
- missing limit handled
- allowed table/column whitelist enforced

For API work, add or update endpoint tests where practical.

## Documentation expectations

When adding new agent behavior:
- update the relevant doc
- keep docs concise
- document decisions, not speculation
- do not rewrite frozen ETL docs unless the task touches them

If a roadmap item is completed, update the corresponding checklist.

## Coding rules

Keep changes small and reversible.

Prefer:
- explicit helper functions
- typed Pydantic request/response models
- clear module boundaries
- defensive validation
- readable error messages

Avoid:
- broad rewrites
- hidden side effects
- implicit database writes
- unvalidated SQL execution
- large prompt changes without tests
- mixing crawler cleanup with agent work

## Secrets and credentials

Never commit secrets.

Do not print:
- API keys
- database credentials
- proxy credentials
- `.env` contents

Use environment variables and `.env.example` placeholders.

## Verification commands

Use relevant commands only.
