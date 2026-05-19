# Database Agent API Contract

This document defines the planned HTTP contract for the database-agent layer.

## Status

- Planning only.
- No endpoint listed here should be treated as implemented.
- Existing search and resume-matching endpoints remain unchanged in this phase.

## Purpose

- Define the internal/demo MVP API contract before implementation starts.
- Keep the public HTTP surface narrow while the database-agent architecture is still being built.
- Make request shapes, response shapes, refusal behavior, and output guarantees explicit.
- Defer SQL grammar and whitelist rules to `docs/agent/sql_contract.md`.
- Defer broader security, auth, rate-limit, and audit policy to `docs/agent/security_model.md`.

## MVP Scope

- Internal/demo MVP contract, not a hardened public external API.
- English natural-language questions only.
- One public MVP endpoint: `POST /agent/ask`.
- Query scope for SQL-capable requests: `clean_jobs` only.
- The agent may route a request to safe SQL/query behavior, guarded resume matching, light small-talk handling, chart generation from SQL results, or safe refusal.
- Generated SQL must be visible in the response according to the rules below.

Out of scope for this contract:

- Public raw SQL submission
- Public preview/query/chart/explanation sub-endpoints
- Authenticated user identity
- Rate limiting policy
- Rendered chart images
- Expanded table access beyond `clean_jobs`
- Public semantic-search mode

## Relationship To Other Agent Docs

This document defines the HTTP contract only.

`docs/agent/sql_contract.md` remains the source of truth for:

- allowed SQL forms
- table and column whitelist rules
- limit rules
- SQL validation outcomes and refusal categories

`docs/agent/security_model.md` remains the source of truth for:

- auth and permissions policy
- rate-limit policy
- logging and auditability policy
- prompt-injection and tool-use boundaries
- security failure handling beyond the HTTP response shape

## Endpoint Inventory

### Public MVP Endpoint

- `POST /agent/ask`

This is the only public database-agent endpoint in MVP.

### Not Public In MVP

The contract does not define public versions of:

- `POST /agent/sql-preview`
- `POST /agent/query`
- `POST /agent/chart`
- `POST /agent/explain`
- `POST /agent/resume-match`

If preview, charting, or other tools are implemented internally, they remain implementation details behind `POST /agent/ask`.

## Endpoint Purpose

`POST /agent/ask` accepts an English question and returns one of the following:

- a validated and executed SQL/query result with table output
- a validated SQL preview without execution
- a resume-matching result
- a light small-talk response
- a safe refusal for unsupported or unsafe behavior

The endpoint may also include:

- a short natural-language summary
- a Vega-Lite-compatible chart spec
- warnings and metadata

## Request Contract

### Required Fields

- `question: string`

### Optional Fields

- `session_id: string | null`
- `user_id: string | null`
- `preview_only: bool = false`
- `include_chart: bool = false`
- `chart_type_hint: string | null`
- `limit: int | null`
- `include_summary: bool = true`
- `debug: bool = false`

### Field Semantics

#### `question`

- Natural-language English question from the client.
- The public API does not accept raw SQL in MVP.

#### `session_id`

- Optional conversation/session identifier supplied by the client.
- If supplied, follow-up questions may use prior session context.
- Session memory is scoped to the session, not to an authenticated user.
- MVP requires persistent session memory across app restarts, but the concrete backend is still deferred.
- The memory layer should remain replaceable; `Mem0` is a current candidate, not a locked requirement.
- `session_id` is not a substitute for authenticated identity and is distinct from the existing resume-matching `user_id`.

#### `user_id`

- Optional user identifier supplied by the client.
- The current repository already uses caller-supplied `user_id` for resume upload and resume matching only.
- In the multi-tool MVP, `user_id` is not required by the SQL/query path but is required for resume-matching tool use.
- `user_id` must not widen SQL scope, change permissions, or alter the `clean_jobs`-only boundary in MVP.
- Resume matching remains a guarded tool path, not a free-form profile or resume-browsing mode.

#### `preview_only`

- When `false`, the endpoint follows the normal SQL-capable path:
  - generate SQL
  - validate SQL
  - execute validated SQL
  - return response
- When `true`, the endpoint:
  - generates SQL
  - validates SQL
  - does not execute SQL
  - returns preview-oriented output

#### `include_chart`

- Explicit client request to include chart output when possible.
- The agent may also infer chart intent from the question even if this field is `false`.
- Inferred chart intent affects tool routing and post-query chart generation only; it does not bypass SQL validation or create a separate execution path.

#### `chart_type_hint`

- Optional client hint such as `bar` or `line`.
- Treated as a preference, not a guarantee.
- MVP chart output should stay within a narrow supported set; `pie` and richer chart types are deferred.

#### `limit`

- Optional client hint for result size.
- Not a promise that the same limit will be executed.
- Final behavior remains subject to SQL validation and limit rules defined in `docs/agent/sql_contract.md`.

#### `include_summary`

- When `true`, the response should include a short natural-language summary when practical.

#### `debug`

- When `true`, the response may expose additional safe debugging fields defined in this contract.
- Debug output must not expose secrets, stack traces, or internal credentials.

### Example Request

```json
{
  "question": "Draw a chart of job count by city.",
  "session_id": "demo-session-123",
  "user_id": "demo-user-123",
  "preview_only": false,
  "include_chart": true,
  "chart_type_hint": "bar",
  "limit": 50,
  "include_summary": true,
  "debug": false
}
```

## Request Handling Flow

The public contract assumes the following high-level flow:

1. Accept an English question.
2. Route the request to an approved internal tool path or refuse unsupported intent.
3. For SQL-capable requests, generate SQL and validate it against the SQL contract.
4. If SQL validation fails, return a refusal and do not execute SQL.
5. If `preview_only=true`, return preview output and do not execute SQL.
6. Otherwise execute only the validated SQL or invoke the selected non-SQL tool path.
7. Return table output, summary output, optional chart output, warnings, and metadata.

Validation must always occur before SQL execution.

Unsafe SQL must never reach execution, and non-SQL tools must remain within their documented boundaries.

Light small-talk requests may be answered through the same endpoint, but they remain intentionally narrow and must not broaden the public contract into a general assistant API.

## Response Contract

All successful HTTP responses for valid requests use a stable envelope:

- `status`
- `question`
- `sql`
- `table`
- `summary`
- `chart`
- `warnings`
- `metadata`
- `error`

### Top-Level Status Values

- `ok`
- `refused`
- `error`

`status="error"` may be used inside a `200` response only if the request itself was valid and the product chooses to represent a handled application error in-band. Unexpected server failures should still use HTTP `500`.

### Top-Level Fields

#### `status`

- `ok` for successful execution, successful preview, successful resume-matching responses, successful light small-talk handling, or empty-result success.
- `refused` for safe refusals such as unsafe SQL or unsupported question types.
- `error` only for handled application-level error states if the implementation chooses to use it.

#### `question`

- Echo of the input question.

#### `sql`

Structured SQL visibility object.

Always include:

- `executed_sql` when execution occurs

Include additionally when `debug=true` or `preview_only=true`:

- `model_generated_sql`
- `validated_sql`
- `executed_sql` when available

SQL field rules:

- `model_generated_sql` is the raw SQL candidate produced before validation.
- `validated_sql` is the SQL after allowed normalization such as default `LIMIT` insertion.
- `executed_sql` is the exact SQL sent to execution.
- If execution is skipped, `executed_sql` may be `null`.
- For non-SQL tool responses, all SQL fields may be `null`.

#### `table`

Structured tabular result object with:

- `columns: string[]`
- `rows: object[]`
- `row_count: integer`

Rules:

- `rows` are row-oriented JSON objects keyed by column name.
- `row_count` is the number of rows returned in `rows`.
- In preview-only responses, `table` should be `null`.
- In refusal responses, `table` should be `null`.
- In resume-matching responses, `table` may be used for normalized match rows.
- In light small-talk responses, `table` should be `null`.

#### `summary`

- Short natural-language explanation or result summary.
- Remains part of the main response.
- No separate explanation endpoint exists in MVP.

#### `chart`

Optional chart payload with:

- `chart_type: string | null`
- `chart_spec: object | null`

Rules:

- Chart output is spec-only.
- The spec should be Vega-Lite-compatible JSON.
- The endpoint does not return rendered images.
- `chart` may be `null` when no chart is requested, inferred, or appropriate.

#### `warnings`

List of human-readable caution messages.

Examples:

- default limit applied
- execution skipped due to preview mode
- chart omitted because result is not a good chart candidate
- salary analytics may be incomplete
- `user_id` required for resume matching but was not provided
- light conversational handling is intentionally narrow in MVP

#### `metadata`

Structured metadata object. MVP fields may include:

- `limit_applied: bool`
- `execution_skipped: bool`
- `trace_id: string`
- `session_id: string | null`
- `user_id: string | null`

Field rules:

- `trace_id` should always be emitted by the server for request tracing and debugging.
- `session_id` may echo the caller-provided session value when present.
- `user_id` may echo the caller-provided value when present.

#### `error`

- `null` on successful responses with `status="ok"`.
- Non-null for refusal or handled error responses.

Recommended shape:

```json
{
  "code": "unsafe_sql",
  "category": "unknown_table",
  "message": "Query rejected because it references a non-approved table."
}
```

Error object rules:

- include safe machine-readable fields such as `code` and `category`
- include a readable message
- do not expose stack traces or internal secrets

## Response Examples

### Successful Query Response

```json
{
  "status": "ok",
  "question": "Draw a chart of job count by city.",
  "sql": {
    "executed_sql": "SELECT cities, COUNT(*) AS job_count FROM clean_jobs GROUP BY cities LIMIT 100"
  },
  "table": {
    "columns": ["cities", "job_count"],
    "rows": [
      {
        "cities": "Ha Noi",
        "job_count": 12
      }
    ],
    "row_count": 1
  },
  "summary": "Ha Noi has 12 jobs in the current database.",
  "chart": {
    "chart_type": "bar",
    "chart_spec": {}
  },
  "warnings": [],
  "metadata": {
    "limit_applied": true,
    "execution_skipped": false,
    "trace_id": "trace-demo-123",
    "session_id": "demo-session-123",
    "user_id": "demo-user-123"
  },
  "error": null
}
```

### Preview-Only Response

```json
{
  "status": "ok",
  "question": "Show me AI engineer jobs in Hanoi.",
  "sql": {
    "model_generated_sql": "SELECT standardized_title, company, cities FROM clean_jobs WHERE standardized_title = 'AI Engineer' AND cities = 'Ha Noi'",
    "validated_sql": "SELECT standardized_title, company, cities FROM clean_jobs WHERE standardized_title = 'AI Engineer' AND cities = 'Ha Noi' LIMIT 50",
    "executed_sql": null
  },
  "table": null,
  "summary": "Preview only. SQL was validated and not executed.",
  "chart": null,
  "warnings": [
    "Execution skipped because preview_only=true."
  ],
  "metadata": {
    "limit_applied": true,
    "execution_skipped": true,
    "trace_id": "trace-demo-124",
    "session_id": "demo-session-123",
    "user_id": "demo-user-123"
  },
  "error": null
}
```

### Safe Refusal Response

```json
{
  "status": "refused",
  "question": "Delete all jobs from the database.",
  "sql": {
    "model_generated_sql": null,
    "validated_sql": null,
    "executed_sql": null
  },
  "table": null,
  "summary": "I can only help with safe read-only exploration of clean_jobs in MVP.",
  "chart": null,
  "warnings": [],
  "metadata": {
    "limit_applied": false,
    "execution_skipped": true,
    "trace_id": "trace-demo-125",
    "session_id": null,
    "user_id": null
  },
  "error": {
    "code": "unsafe_sql",
    "category": "disallowed_statement",
    "message": "Query rejected because it attempts a non-read-only database operation."
  }
}
```

### Resume-Matching Response

```json
{
  "status": "ok",
  "question": "Match my resume to backend jobs.",
  "sql": {
    "model_generated_sql": null,
    "validated_sql": null,
    "executed_sql": null
  },
  "table": {
    "columns": ["title", "company", "cities", "match_score"],
    "rows": [
      {
        "title": "Backend Developer",
        "company": "Tech Corp",
        "cities": ["Ha Noi"],
        "match_score": 0.82
      }
    ],
    "row_count": 1
  },
  "summary": "I found 1 strong backend-oriented match for your stored resume.",
  "chart": null,
  "warnings": [],
  "metadata": {
    "limit_applied": false,
    "execution_skipped": false,
    "trace_id": "trace-demo-126",
    "session_id": "demo-session-123",
    "user_id": "demo-user-123"
  },
  "error": null
}
```

### Light Small-Talk Response

```json
{
  "status": "ok",
  "question": "What can you do?",
  "sql": {
    "model_generated_sql": null,
    "validated_sql": null,
    "executed_sql": null
  },
  "table": null,
  "summary": "I can help you explore clean_jobs with safe read-only questions, show the SQL I used, return tables, generate simple chart specs from results, and route resume-matching requests when user_id is provided.",
  "chart": null,
  "warnings": [
    "Light conversational handling is intentionally narrow in MVP."
  ],
  "metadata": {
    "limit_applied": false,
    "execution_skipped": true,
    "trace_id": "trace-demo-127",
    "session_id": null,
    "user_id": null
  },
  "error": null
}
```

## HTTP Status Contract

### `200 OK`

Use `200 OK` when the request payload is valid and the system returns any of the following:

- normal query results
- empty query results
- preview-only results
- successful resume-matching results
- light small-talk responses
- safe refusals

### `400 Bad Request`

Use `400 Bad Request` for invalid request payloads, such as:

- missing required fields
- blank `question`
- invalid field types
- unsupported request field values

### `500 Internal Server Error`

Use `500 Internal Server Error` for unexpected internal failures.

The API contract should not promise stack traces or internal debug details in `500` responses.

## Refusal And Error Semantics

### Safe Refusal Behavior

If the request is valid but the intended operation is unsupported or unsafe, the endpoint should:

- return `200 OK`
- set `status="refused"`
- include a safe machine-readable `error.code`
- include a safe machine-readable `error.category` when available
- include a readable explanation
- not execute SQL

Examples of refusal-level cases:

- unsafe SQL shape after generation
- unsupported question type
- request to mutate or destroy data
- request outside MVP `clean_jobs` scope
- resume-matching request without `user_id`
- broad unsupported assistant-style requests outside the bounded tool set

### Empty Result Behavior

Empty results are still successful query outcomes.

The endpoint should:

- return `200 OK`
- set `status="ok"`
- return `table.rows=[]`
- return `table.row_count=0`
- include a short summary or warning when useful

## Chart Output Rules

- Chart output is optional in MVP.
- The endpoint should support both:
  - explicit chart requests through `include_chart=true`
  - inferred chart intent from the question
- The chart contract should remain practical:
  - based on executed and normalized SQL/table results only
  - intended mainly for grouped or clearly chartable tabular results
  - limited to a small MVP chart set such as `bar` and `line`
  - allowed to return warnings instead of a chart when the result is a weak chart candidate

The contract does not promise:

- rendered charts
- advanced dashboard interactions
- multi-step chart editing workflows

## Session Memory Rules

- Session memory is supported through caller-provided `session_id`.
- Follow-up questions may use prior context from the same session.
- MVP requires session memory that persists across app restarts, but the concrete backend remains deferred and should stay replaceable.
- Memory is intended for short follow-up workflows such as:
  - "Show me AI engineer jobs in Hanoi."
  - "Now filter to senior roles."
  - "Draw that as a chart."
  - "Which ones require Python?"
- The contract does not promise identity-based personalization or unrestricted long-term recall beyond the bounded MVP follow-up use cases.
- `session_id` should be treated as a conversation key, not as a user profile key.

## User Identity Boundary

- The SQL/query path does not require `user_id`.
- The existing repository already uses `user_id: str` in the resume-matching flow backed by `user_profiles.user_id`.
- That `user_id` is caller-supplied and currently acts as the lookup key for stored resume text and embeddings.
- In MVP, the SQL/query path should ignore `user_id` for authorization, filtering, and schema access decisions.
- Resume-matching tool use may require `user_id`, but that must not change SQL table scope or SQL permissions.

## Public Boundary Rules

- The public MVP contract accepts English questions only.
- Raw SQL submission is excluded from the public API.
- Unsafe SQL must never be executed.
- `clean_jobs` is the only queryable product-facing table in MVP.
- Resume matching is a guarded equal branch behind the same endpoint and does not create a second public API.
- Resume matching and chart generation may exist as internal tool paths behind the same endpoint, but they do not create additional public endpoints in this contract.
- The database agent uses a LangChain-native provider path internally, but that remains an internal implementation detail and is not part of the public HTTP contract.

## Validation And Safety Notes

- The API contract should state that validation happens before execution.
- The API contract should state that only validated SQL may execute.
- The API contract should not duplicate the detailed SQL whitelist, blocked syntax table, or validator normalization rules from `docs/agent/sql_contract.md`.
- The API contract may reference refusal categories from the SQL contract when describing response behavior.

## Test Cases For This Contract

The implementation and future tests should validate at least the following behaviors:

- happy-path English question returns `status="ok"`, executed SQL, table rows, and summary
- `preview_only=true` returns validated SQL, skips execution, and sets `execution_skipped=true`
- `debug=true` exposes `model_generated_sql`, `validated_sql`, and `executed_sql` when available
- explicit `include_chart=true` can return a chart spec
- chart-intent questions may return a chart spec even without `include_chart=true`
- non-chartable results may return `chart=null` with warnings
- light small-talk requests may return `status="ok"` with summary text and no SQL execution
- resume-matching requests with `user_id` can return normalized match rows without SQL execution
- resume-matching requests without `user_id` are refused safely
- unsafe or unsupported requests return `200` with `status="refused"` and safe machine-readable error fields
- empty results return `status="ok"` with empty rows
- malformed requests return `400`
- same-session follow-ups may use prior session context through `session_id`
- `trace_id` is always present in metadata
- `limit_applied` and `execution_skipped` are returned consistently

## Versioning Notes

- This document defines the MVP contract only.
- Future versions may add internal tools, richer chart behavior, auth, rate limiting, or broader schema access.
- Future changes should preserve the single-endpoint MVP story unless a documented product decision changes that boundary.
