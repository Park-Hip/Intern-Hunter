# Database Agent SQL Contract

This document defines what SQL the database agent may generate, validate, and execute against the existing job-finder database.

## Purpose

- Establish safe SQL boundaries before any text-to-SQL implementation begins.
- Separate allowed analytical behavior from unsafe or unsupported database access.

## Contract Goals

- Keep MVP SQL validation small, explicit, and highly testable.
- Support English-to-SQL exploration over structured `clean_jobs` data only.
- Prevent write operations, schema changes, unrestricted table access, and fuzzy free-text SQL behavior.
- Make generated SQL visible to the user and ensure only validated SQL is executed.
- Keep SQL as one bounded tool path inside the broader multi-tool MVP without allowing charting, small-talk, or resume matching to widen SQL scope.

## Allowed Query Types

- MVP allows plain single-statement `SELECT` queries only.
- `SELECT` queries may include:
  - `WHERE`
  - `GROUP BY`
  - `ORDER BY`
  - `LIMIT`
  - approved aggregate functions
- MVP does not allow:
  - `WITH` / CTE queries
  - joins
  - subqueries
  - set operations such as `UNION`, `INTERSECT`, or `EXCEPT`

Allowed examples:

```sql
SELECT standardized_title, company, cities
FROM clean_jobs
WHERE job_level = 'Junior'
ORDER BY created_at DESC
LIMIT 50;
```

```sql
SELECT job_level, COUNT(*) AS job_count
FROM clean_jobs
GROUP BY job_level
ORDER BY job_count DESC
LIMIT 20;
```

## Read-Only Rules

- Only validated read-only `SELECT` queries may execute.
- The validator must reject any statement that is not a single `SELECT`.
- The validator must reject any query that attempts to mutate data, schema, or database configuration.
- The validator must reject multiple SQL statements in one request.

Always blocked statement types:

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

## Table Whitelist

- MVP table whitelist:
  - `clean_jobs`
- No other table is agent-queryable in MVP.
- References to internal, audit, raw, or operational tables must always be rejected.
- Future table expansion is deferred until it is documented explicitly.

## Column Whitelist

- Approved MVP SQL columns in `clean_jobs`:
  - `standardized_title`
  - `company`
  - `cities`
  - `job_level`
  - `tech_stack`
  - `technical_competencies`
  - `salary_min`
  - `salary_max`
  - `currency`
  - `is_salary_negotiable`
  - `experience`
  - `english_requirement`
  - `domain_knowledge`
  - `is_internship`
  - `created_at`

Columns present in the database but not agent-queryable in MVP SQL:

- `description`
- `requirement`
- `benefit`
- `embedding`
- `min_gpa`

Column whitelist rules:

- Every selected, filtered, grouped, or ordered column must be explicitly whitelisted.
- `SELECT *` is not allowed.
- Unknown or non-whitelisted columns must always be rejected.

## Join Rules

- Joins are not allowed in MVP.
- Aliases that imply self-joins or multi-table query shapes are also out of scope for MVP validation.

## Aggregation Rules

- Allowed aggregate functions:
  - `COUNT`
  - `MIN`
  - `MAX`
  - `AVG`
  - `SUM`
- `GROUP BY` is allowed only on approved structured columns from the whitelist.
- `ORDER BY` is allowed on approved grouped columns, approved selected columns, or approved aggregate outputs.
- Chart-oriented grouped queries are part of MVP, but they must remain within the same single-table, structured-field-only rules.
- Chart generation must consume executed and normalized SQL results only; it must not create an alternate query or execution path.

Grouping restrictions:

- Do not group by long-text fields.
- Do not use `technical_competencies` as the main field for broad skill-frequency analytics.
- Do not use `domain_knowledge` as a grouped or chart dimension in MVP.
- Use structured dimensions such as `cities`, `job_level`, `company`, `standardized_title`, `is_internship`, or `currency` where appropriate.

Array/JSON field policy:

- `cities` and `tech_stack` are queryable only through constrained membership-style patterns defined by the validator and implementation.
- `technical_competencies` and `domain_knowledge` must not become free-form JSON search surfaces in MVP.
- Generic JSON traversal, arbitrary JSON/array functions, JSON path expressions, and broad unnest-style query patterns are out of scope for MVP and should be rejected.

## LIMIT And Result Size Rules

- Queries without `LIMIT` must receive a safe default `LIMIT 50` during validation.
- Maximum allowed `LIMIT` for row-returning queries: `200`.
- Maximum allowed `LIMIT` for grouped or chart-oriented result sets: `100`.
- Queries without explicit `ORDER BY` are allowed.
- Excessive requested limits must not execute unchanged.

Validator policy for excessive limits:

- If a query requests a `LIMIT` above the allowed maximum, validation should fail rather than silently rewrite the request to another number.

## Unsafe Query Refusal Rules

- Reject multiple statements.
- Reject any non-`SELECT` statement.
- Reject `WITH` / CTE queries.
- Reject joins.
- Reject subqueries.
- Reject unknown tables.
- Reject unknown or non-whitelisted columns.
- Reject `SELECT *`.
- Reject substring-style text matching such as `LIKE`, `ILIKE`, regular-expression matching, or equivalent text-search operators/functions.
- Reject filters over long-text fields such as `description`, `requirement`, and `benefit`.
- Reject unsupported SQL functions or query shapes outside this MVP contract.

MVP query-shape policy:

- Prefer exact or simple structured filtering over approved fields.
- Do not use free-text SQL matching as a fallback behavior in MVP.
- Resume matching, small-talk, and other non-SQL tool paths must not bypass or expand this SQL contract.

## Validation Outcomes

- Validation may perform minimal normalization only:
  - trim surrounding whitespace
  - remove a trailing semicolon
  - add the default `LIMIT` when missing
- Validation must not broadly rewrite query structure to make an invalid query pass.
- Executed SQL must always be the validated SQL, not the raw model-generated SQL.

Recommended internal validation categories:

- `disallowed_statement`
- `multi_statement`
- `unknown_table`
- `unknown_column`
- `non_whitelisted_column`
- `missing_limit`
- `excessive_limit`
- `forbidden_wildcard_select`
- `forbidden_join`
- `forbidden_cte`
- `forbidden_subquery`
- `forbidden_text_match`
- `forbidden_long_text_reference`
- `unsupported_query_form`

User-facing behavior:

- Generated SQL should always be visible to the user.
- If validation modifies the SQL by adding a default `LIMIT`, the validated SQL should be shown to the user before or alongside execution results.
- Refusals should explain the reason in readable language without exposing unnecessary internals.
