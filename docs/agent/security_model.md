# Database Agent Security Model

This document defines the MVP security model for the future database-agent layer.

## Status

- Planning only.
- Security requirements here are future constraints, not implemented guarantees.
- This document defines the minimum guardrail model required before the database-agent MVP should execute SQL.

## Purpose

- Document the safety model before enabling text-to-SQL and tool-assisted database exploration.
- Make security boundaries explicit for request screening, prompts, SQL validation, execution, output generation, and logging.
- Keep MVP guardrails narrow, practical, and aligned with the bounded multi-tool MVP: SQL over `clean_jobs`, result-driven charting, light small-talk handling, and resume matching through an explicit user-scoped tool.

## Security Goals

The MVP security model should guarantee the following:

- user input is treated as untrusted
- session context is treated as untrusted
- model output is treated as untrusted
- the agent cannot widen schema scope beyond documented MVP boundaries
- only validated read-only SQL may execute
- unsafe or unsupported requests are refused instead of executed
- prompt behavior never replaces SQL validation
- outputs avoid leaking secrets, credentials, or unnecessary internal details
- logs are useful for debugging without becoming a raw secret dump

## Threat Model

The MVP agent is exposed to natural-language input that can attempt to:

- request unsafe SQL such as `DELETE`, `UPDATE`, or schema changes
- trick the model into ignoring its schema or safety instructions
- ask for access to non-MVP tables such as `raw_jobs`, audit tables, or operational tables
- request free-text search behavior over fields that are intentionally blocked in MVP SQL
- request broad assistant-style behavior outside the bounded tool set
- attempt to use a resume-scoped request to widen database access or browse user-profile data
- exploit follow-up memory by inserting malicious or misleading prior context
- request excessive result sizes or overly broad database scans
- extract internal stack traces, secrets, or configuration details through debug or error behavior

The MVP model does not attempt to solve every possible prompt-security problem. It focuses on preventing unsafe SQL execution, keeping tool access bounded, and keeping product-facing scope narrow.

## Guardrail Model

The MVP safety story is layered:

1. **Pre-agent guardrail**
   - lightweight request screening and bounded request shaping
   - not a full policy engine
   - not a replacement for SQL validation

2. **Constrained prompt/context**
   - the model sees only approved schema and tool scope
   - no silent schema widening

3. **Bounded ReAct loop**
   - limited tool set
   - limited loop depth
   - no autonomous execution privileges

4. **Hard SQL validation gate**
   - mandatory before execution
   - deterministic and outside agent autonomy

5. **Read-only execution boundary**
   - executor accepts validated SQL only

6. **Safe output and refusal shaping**
   - protect against secret leaks and overexposed errors

This layered model is the MVP guardrail baseline.

## SQL Safety Model

SQL safety is the primary execution guardrail for MVP.

Security requirements:

- SQL generation is not trusted by itself
- every generated SQL candidate must be validated before execution
- the validator is the source of truth for allowed SQL shape
- the executor must consume validated SQL only
- invalid or unsafe SQL must produce refusal behavior and must not execute

The detailed SQL rules belong to `docs/agent/sql_contract.md`, including:

- allowed query forms
- blocked statements
- table whitelist
- column whitelist
- default `LIMIT` behavior
- refusal categories

This security model depends on the SQL contract being enforced at runtime rather than treated as prompt guidance only.

## Prompt-Injection Risks

Prompt injection is in scope for MVP because the system accepts untrusted natural-language input.

Minimum MVP stance:

- user questions are untrusted
- session memory is untrusted
- model outputs are untrusted until validated
- prompt instructions must not allow the model to self-expand access beyond the documented schema dictionary
- `session_id` is untrusted conversation context, not trusted identity

Minimum MVP mitigations:

- provide the model only the approved `clean_jobs` schema context and field guidance
- keep prompt instructions explicit about MVP scope
- never rely on prompt instructions alone to block dangerous SQL
- validate SQL after generation regardless of how safe the prompt appears
- keep follow-up memory bounded and product-focused rather than replaying long unfiltered transcripts

Prompt injection does not become a reason to widen guardrail complexity beyond MVP. It is addressed by layered controls:

1. pre-agent guardrail
2. constrained schema/context
3. SQL validation
4. execution boundary
5. safe refusal/error shaping

## Tool-Use Boundaries

The public MVP contract exposes one endpoint: `POST /agent/ask`.

Internal components behave like tools in MVP, but boundary rules remain:

- the public API accepts English natural-language questions only
- raw SQL submission is excluded from the public API
- `clean_jobs` is the only product-facing query table
- resume matching is allowed only through a bounded tool path and must not become free-form profile browsing
- small-talk handling is intentionally narrow and must not become a general assistant mode
- chart generation is a post-query internal step, not a second public execution path
- existing resume-matching `user_id` handling is separate and must not be repurposed as a SQL permission or table-scope control
- if `user_id` is accepted by the contract, it may enable resume-tool use but must not widen SQL scope, permissions, or table access in MVP

Any tool path should preserve the rule that no tool may bypass SQL validation where SQL is involved or broaden scope silently.

## Read-Only Execution Guarantees

The runtime architecture must preserve a strict execution boundary:

- SQL generation produces a candidate, not executable truth
- validation decides whether the candidate is safe and what SQL, if any, may run
- execution accepts validated SQL only
- unsafe SQL must never reach the executor

Read-only execution guarantees for MVP:

- no write SQL
- no schema mutation
- no admin/configuration SQL
- no multi-statement execution
- no non-whitelisted table access
- no non-whitelisted column access

Preview mode is also part of the safety model:

- `preview_only=true` validates SQL
- preview mode does not execute SQL
- preview responses must make the skipped execution explicit

## Secrets Handling

The database-agent MVP must not expose secrets through prompts, logs, errors, or debug output.

Minimum requirements:

- never include API keys, DB credentials, or `.env` contents in agent responses
- keep prompt/context payloads free of secret configuration values
- debug output may expose SQL artifacts allowed by the API contract, but not stack traces, secrets, or raw credentials
- refusal and error messages should remain readable without leaking internal implementation details

This matches the repository-wide secret-handling rules in `AGENTS.md`.

## Logging And Auditability

The MVP is internal/demo oriented, so logging should be useful and lightweight rather than overbuilt.

Recommended log or trace events:

- request received
- pre-agent guardrail passed or refused
- session context used or absent
- tool selected or refusal path selected
- SQL generated
- SQL validated or refused
- preview skipped execution
- SQL execution started and completed
- resume-matching tool invoked or refused
- response status emitted

Recommended log fields:

- trace identifier on every request
- request mode flags such as preview/debug/chart
- refusal category when applicable
- row count when execution succeeds

Logging guidance:

- validated SQL should be logged for debugging and auditability in internal/demo MVP
- executed SQL should be logged when execution occurs
- raw model-generated SQL should be logged only in debug flows or refusal-analysis paths
- logs should not include secrets or raw credentials
- logging policy should avoid dumping entire sensitive runtime objects when smaller structured fields are enough

Observability guidance:

- observability should stay generic at the architecture level
- tools such as Langfuse or MLflow may be used as examples for tracing and evaluation support
- they should not be documented as hard MVP dependencies in the security contract

## Timeout Policy

Initial MVP timeout policy:

- tool routing and SQL generation: 20 seconds
- SQL validation: 1 second
- SQL execution: 5 seconds
- answer generation: 10 seconds
- chart generation: 5 seconds
- target end-to-end request budget: 30 seconds

Timeout behavior:

- timeouts must fail safely
- timeouts must not trigger unvalidated or partial SQL execution
- timeout responses should return bounded refusal or error behavior without leaking internals

The architecture doc should define the logging seam. This document defines the minimum policy expectation.

## Failure And Refusal Behavior

The MVP should prefer safe refusal over risky fallback behavior.

Security-sensitive refusal cases include:

- unsafe SQL generation result
- unsupported question type
- request for blocked tables or fields
- request to mutate or destroy data
- request outside MVP scope
- resume-matching request without the required `user_id`
- request to inspect raw resume/profile storage instead of using the bounded matching capability
- broad unsupported assistant-style or semantic-search-style requests outside the bounded MVP tool set

Required refusal behavior:

- do not execute SQL
- return a safe machine-readable refusal category when available
- return a human-readable explanation
- avoid raw stack traces or internal exception dumps

Unexpected runtime failures may still return server errors, but those should remain bounded and non-secret-bearing.

## Ownership Boundaries

This document does not replace the other agent docs.

Ownership split:

- `docs/agent/sql_contract.md`
  - exact SQL rules and validation categories

- `docs/agent/api_contract.md`
  - public request/response shape and HTTP behavior

- `docs/agent/architecture.md`
  - runtime placement of validation, execution, answer generation, charting, memory, and logging seams

- `docs/agent/data_dictionary.md`
  - field semantics and query-facing interpretation of `clean_jobs`

This document owns the broader trust model and minimum guardrail requirements around those pieces.

## Open Security Questions

- What bounded session-memory retention policy is appropriate for MVP if memory is stored outside the database?
