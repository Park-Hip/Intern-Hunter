# InternHunter Data Agent Data Dictionary

## 1. Title

InternHunter Data Agent Data Dictionary

## 2. Purpose

This document explains how the InternHunter Data Agent should interpret the `clean_jobs` table during the MVP phase.

It is a practical query-facing dictionary, not a schema migration document. It defines what the agent should treat as reliable, what it should avoid, and how it should answer common job-search and analytics questions.

## 3. MVP Allowed Data Scope

- MVP allowed table: `clean_jobs` only
- Do not expose `raw_jobs`, crawler artifacts, audit logs, or unrestricted database tables
- Do not include source URLs or job links in MVP responses
- Do not assume access to fields outside `clean_jobs` unless this document is updated later

Important scope note:

- `raw_jobs` remains internal ETL evidence and is not agent-queryable
- `company` is exposed to the agent only through `clean_jobs.company`
- `clean_jobs.company` is a product-facing copy of the direct raw employer fact, added so the MVP agent can stay on `clean_jobs` only

## 4. `clean_jobs` Table Overview

`clean_jobs` is the structured job table produced from the ingestion pipeline. For MVP, it is the only table the agent may query.

The table is suitable for:

- role and location filtering
- job-level filtering and counts
- tech-stack filtering and aggregation
- limited salary analytics with caution
- recency questions using `created_at`

The table is less suitable for:

- unrestricted raw-database browsing
- source-level inspection
- broad analytics over long-form text fields
- semantic-search-first answers for structured analytics questions

## 5. Column Dictionary

### `standardized_title`

- Meaning: Canonical role title for a job
- Expected type / shape: string
- Example values: `AI Engineer`, `Data Scientist`, `Backend Developer`
- Reliability label: high
- Agent usage: primary role/title filter and display field
- Query guidance: use for role filters, grouping, and counts; prefer over raw title references

### `company`

- Meaning: employer name
- Expected type / shape: string or null
- Example values: `TopCV`, `Tech Corp`, `FPT Software`
- Reliability label: medium
- Agent usage: display field, company filtering, grouping, and counts
- Query guidance: query `clean_jobs.company` only; do not expose or join to `raw_jobs` for agent access

### `cities`

- Meaning: normalized job locations
- Expected type / shape: JSON array of strings
- Example values: `["Ha Noi"]`, `["Ho Chi Minh", "Remote"]`
- Reliability label: high
- Agent usage: location filtering, grouping, and charting
- Query guidance: use canonical city names; support city counts and city filters

### `job_level`

- Meaning: normalized seniority or role level
- Expected type / shape: string
- Example values: `Intern`, `Fresher`, `Junior`, `Senior`, `Manager`
- Reliability label: high
- Agent usage: filtering, grouping, counts, and charting
- Query guidance: reliable enough for MVP questions about junior, senior, internship, and job count by level

### `tech_stack`

- Meaning: specific tools, technologies, or technical skills
- Expected type / shape: JSON array of strings
- Example values: `["Python", "SQL", "AWS"]`, `["PyTorch", "LLM", "Docker"]`
- Reliability label: high
- Agent usage: primary field for skill filtering and broad skill analytics
- Query guidance: use first for direct skill filters and for frequency analysis such as top skills

### `technical_competencies`

- Meaning: normalized actions or capability phrases from the job description
- Expected type / shape: JSON array of strings
- Example values: `["Fine-tune LLMs", "Evaluate Models", "Deploy Models"]`
- Reliability label: medium
- Agent usage: useful for exact job detail display and future resume-matching/tool use
- Query guidance: do not use as the primary field for broad skill-frequency analytics; use carefully for capability-style interpretation, not top-skill charts

### `description`

- Meaning: main job description text
- Expected type / shape: text
- Example values: long-form job description
- Reliability label: medium
- Agent usage: stored source text for offline inspection and future non-SQL behaviors
- Query guidance: not agent-queryable in MVP SQL; do not use for filtering, aggregation, grouping, or charts

### `requirement`

- Meaning: job requirement text
- Expected type / shape: text
- Example values: long-form requirements list
- Reliability label: medium
- Agent usage: stored source text for offline inspection and future non-SQL behaviors
- Query guidance: not agent-queryable in MVP SQL; use structured fields such as `tech_stack` instead of free-text matching

### `benefit`

- Meaning: benefits text for the role
- Expected type / shape: text
- Example values: long-form benefits list
- Reliability label: low
- Agent usage: stored source text only
- Query guidance: not agent-queryable in MVP SQL; not recommended for analytics, grouping, or charts

### `salary_min`

- Meaning: lower bound of salary when structured salary is available
- Expected type / shape: float or null
- Example values: `1000`, `15000000`
- Reliability label: medium
- Agent usage: optional salary analytics
- Query guidance: not a default display field; exclude null or negotiable-only rows from averages and mention incomplete coverage

### `salary_max`

- Meaning: upper bound of salary when structured salary is available
- Expected type / shape: float or null
- Example values: `1500`, `25000000`
- Reliability label: medium
- Agent usage: optional salary analytics
- Query guidance: not a default display field; exclude null or negotiable-only rows from averages and mention incomplete coverage

### `currency`

- Meaning: salary currency
- Expected type / shape: string
- Example values: `VND`, `USD`
- Reliability label: medium
- Agent usage: interpret salary values correctly
- Query guidance: include when presenting salary analytics; avoid mixing currencies silently

### `is_salary_negotiable`

- Meaning: whether salary is listed as negotiable rather than numeric
- Expected type / shape: boolean
- Example values: `true`, `false`
- Reliability label: high
- Agent usage: salary filtering and salary-data quality checks
- Query guidance: treat negotiable rows as non-numeric for averages unless explicitly handled separately

### `experience`

- Meaning: minimum experience requirement in years when captured numerically
- Expected type / shape: float or null
- Example values: `0`, `1`, `2`, `3`
- Reliability label: medium
- Agent usage: optional filtering and answer support
- Query guidance: usable for simple filters, but the agent should mention uncertainty if interpreting it too precisely

### `english_requirement`

- Meaning: English-language requirement if present
- Expected type / shape: string or null
- Example values: `TOEIC 600`, `Fluent`, `Good English communication`
- Reliability label: medium
- Agent usage: display, filtering, and limited answer support
- Query guidance: use as a text-based requirement field, not as a strongly normalized analytic dimension

### `domain_knowledge`

- Meaning: business domains or concept areas associated with the role
- Expected type / shape: JSON array of strings
- Example values: `["Banking"]`, `["NLP", "LLM", "Computer Vision"]`
- Reliability label: medium
- Agent usage: thematic filtering and qualitative answer support
- Query guidance: useful for domain-oriented exploration, filtering, and qualitative answers, but do not use it as a grouped/chart dimension in MVP

### `is_internship`

- Meaning: whether the role is an internship or fresher-style role
- Expected type / shape: boolean
- Example values: `true`, `false`
- Reliability label: high
- Agent usage: internship filtering and counts
- Query guidance: can support internship-related questions directly; keep consistent with `job_level` if both are used

### `created_at`

- Meaning: row creation timestamp for the clean job record
- Expected type / shape: timezone-aware timestamp
- Example values: `2026-05-16 10:00:00+00:00`
- Reliability label: high
- Agent usage: recency and latest-job questions
- Query guidance: use only for recency/latest-job questions; do not introduce broader time semantics unless future documentation confirms them

## 6. Default Result Fields

Desired default job result fields:

- `standardized_title`
- `company`
- `cities`
- `job_level`
- `tech_stack`
- `technical_competencies`

Strict MVP default result fields available from `clean_jobs`:

- `standardized_title`
- `company`
- `cities`
- `job_level`
- `tech_stack`
- `technical_competencies`

Default-field notes:

- `technical_competencies` is useful for exact job detail display and future resume-matching workflows
- `technical_competencies` should not be used for broad skill-frequency analytics
- `salary_min` and `salary_max` are not default display fields because they are often missing

## 7. Query Guidance

- Use structured fields only for MVP SQL filtering and aggregation
- Use SQL-based filtering and aggregation for structured analytics questions
- Do not use semantic search as the default path for structured analytics
- Use `created_at` only for recency/latest-job questions
- Mention uncertainty when using incomplete, sparse, or estimated fields

## 8. Skill-Query Guidance

For direct skill filters such as "jobs requiring Python and SQL":

- use `tech_stack`
- do not fall back to `requirement` or `description` in MVP SQL

For broad skill analytics such as "most common skills":

- use `tech_stack`
- do not use `technical_competencies` as the primary analytics field

For vague capability-style questions such as "Find jobs where I can fine-tune models":

- clarify that this is outside the first SQL-contract slice of MVP
- explain that richer semantic search is deferred until after the SQL/query guardrails are stable

## 9. Role-Query Guidance

- Use `standardized_title` for role filters
- Do not rely on a raw title field for MVP role filtering
- Use `job_level` and `is_internship` for seniority or internship-style questions

## 10. Salary Guidance

- `salary_min` and `salary_max` are not default display fields
- Salary analytics should exclude rows with missing salary values
- Salary analytics should exclude negotiable-only salaries from averages
- The agent should mention that salary coverage may be incomplete
- The agent should avoid silently combining different currencies

## 11. City/Location Guidance

Use these canonical city names in MVP:

- `Ha Noi`
- `Ho Chi Minh`
- `Da Nang`
- `Remote`

Location guidance:

- use `cities` for location filtering and city-level charts
- normalize user wording to canonical city names when possible
- prefer city-level aggregation over long-text location interpretation

## 12. Chart Guidance

MVP chart questions should use aggregated results only, not raw long-text fields.

Recommended MVP chart types:

- job count by city
- job count by `job_level`
- top `tech_stack` frequencies
- salary range by city

Chart guidance:

- use grouped counts or grouped salary summaries
- keep chart generation result-driven from executed and normalized table results
- avoid charts based directly on `description`, `requirement`, or `benefit`
- note incomplete salary coverage when charting salary data

## 13. Reliability Summary

High reliability:

- `standardized_title`
- `cities`
- `job_level`
- `tech_stack`
- `is_internship`
- `created_at`
- `is_salary_negotiable`

Medium reliability:

- `technical_competencies`
- `description`
- `requirement`
- `salary_min`
- `salary_max`
- `currency`
- `experience`
- `english_requirement`
- `domain_knowledge`

Low reliability or unavailable in MVP scope:

- `benefit`

The agent should mention uncertainty whenever it relies on medium- or low-reliability fields for conclusions.

## 14. Fields Not Allowed Or Not Recommended For MVP

- Any table outside `clean_jobs`
- Any source URL or job link field
- Raw crawler artifacts
- Audit or operational tables
- `description`
- `requirement`
- `benefit`
- `embedding`
- `min_gpa`
- Long-text SQL filtering
- Long-text fields as primary chart dimensions
- `technical_competencies` as the main field for broad skill-frequency analytics
- Unrestricted raw database access

## 15. Open Questions

- How should canonical city mapping handle mixed-language user inputs such as `Hanoi` versus `Ha Noi`?
