# InternHunter Data Agent Vision

This document defines the product vision for the InternHunter Data Agent phase.

## 1. Title

InternHunter Data Agent

## 2. Product Summary

InternHunter Data Agent is a SQL-first job-database assistant for job seekers. Its primary role is to help users explore the existing job dataset in natural English without requiring them to write SQL manually.

For MVP, the agent is a bounded multi-tool assistant rather than a broad general assistant. It stays centered on safe, read-only exploration of `clean_jobs` while also supporting closely related output and user-scoped workflows through explicit guarded tool paths.

The first-shipped MVP identity is:

- a SQL-first database exploration assistant
- a job-market analytics assistant over structured `clean_jobs` fields
- a bounded multi-tool assistant that can choose between SQL querying, result-driven charting, light small-talk handling, and guarded resume matching

For the first SQL-contract stage of MVP, the SQL exploration path is intentionally narrow:

- structured-field SQL only
- `clean_jobs` only
- no free-text SQL matching over long-form fields
- no write or schema-changing behavior

## 3. Target Users

- Job seekers who want to search jobs more naturally than keyword-only search
- Job seekers who want to understand hiring patterns, common skills, and market trends from collected job data
- Reviewers, recruiters, or peers evaluating the project as a portfolio demo of agent + database + charts

## 4. Problem Statement

Job seekers should not need to know the database structure or write SQL to explore the job dataset. They need a safe way to move from natural-language questions to reliable tables, summaries, and simple chart-ready outputs without being exposed to raw SQL interfaces or unstable schema details.

The current opportunity is to turn collected jobs into searchable insights, not just records. The MVP should help users move quickly from questions to answers while staying within a very narrow and testable SQL safety boundary.

## 5. Product Goals

- Remove the need for users to write SQL manually
- Let users explore job-market data quickly through English questions
- Turn collected jobs into useful insights, not only raw listings
- Show users the SQL the system used when the SQL path is selected
- Support simple result-driven charts from executed SQL results
- Support guarded resume matching through the same entrypoint when the request is clearly user-scoped
- Become a strong portfolio demo of agent + database + charts
- Route requests to the right bounded tool path instead of forcing every question through one behavior

## 6. Core User Capabilities

- Ask English questions about the job database
- See the SQL the agent generated for SQL-capable requests
- Receive read-only query results as tables
- Receive short natural-language summaries of results
- Request simple chart or graph specs from executed query results
- Explore job-market patterns such as counts, common skills, and filtered job groups
- Use resume matching through the same agent entrypoint when the request is clearly user-scoped and `user_id` is available
- Exchange light conversational messages such as greetings, thanks, or "what can you do?" prompts without widening the agent into a broad assistant

Future capability direction:

- Expand tool coverage only after the first SQL/query, charting, and resume-tool contracts and guardrails are stable

## 7. MVP Scope

- English-only interface
- Query `clean_jobs` only
- Use a predefined schema dictionary
- Generate safe SQL
- Execute read-only SQL
- Show generated SQL to the user
- Restrict SQL filtering to approved structured fields
- Return tables
- Return short natural-language summaries
- Generate chart specs from executed query results
- Refuse unsafe database operations
- Route questions through a bounded LangChain ReAct-style loop with explicit tool limits
- Keep the first ReAct/tool-routing loop tight, with 2-3 tool steps maximum
- Keep SQL generation as a distinct internal component
- Keep SQL validation as a hard deterministic boundary outside agent autonomy
- Allow resume matching as an MVP tool path when the request is user-scoped and `user_id` is available
- Support persistent session follow-up context through `session_id`
- Keep `session_id` as conversation context only, not as authenticated user identity
- Accept `user_id` as the caller-supplied identifier required for resume-matching tool use and available for future user-scoped tools
- Support only light small-talk handling in MVP: greetings, thanks, brief acknowledgements, and simple capability questions

Constraints for MVP:

- Do not touch ETL or crawler code unless a blocking bug appears
- Do not change the database schema
- Keep `clean_jobs` as the only queried table in MVP
- Keep first-stage SQL validation narrow and highly testable
- Keep public behavior to one `POST /agent/ask` endpoint
- Keep public input to English natural-language questions only
- Use a LangChain-native provider path for agent generation/orchestration
- Use a single provider configuration first and defer fallback-provider logic until later hardening
- Keep chart generation result-driven from executed SQL/table results even when chart intent is inferred from the question
- Keep chart generation deterministic-first or hybrid from normalized results rather than creating a second free-form reasoning path
- Keep summary generation grounded in executed results, using deterministic-first or hybrid behavior rather than unconstrained answer synthesis
- Keep session memory persistent across app restarts, but leave the concrete backend replaceable; `Mem0` is only a current candidate
- Keep resume-matching `user_id` handling separate from SQL table scope and SQL permissions
- Keep existing resume matching storage and API boundaries intact even if the agent can call the same underlying capability

## 8. Demo Questions

- Show me AI engineer jobs in Hanoi.
- Count jobs by city.
- What skills are most common for data jobs?
- Show jobs requiring Python and SQL.
- Draw a chart of job count by city.
- Match my resume to backend jobs.
- What can you do?

## 9. Safety/Refusal Requirements

- Refuse write SQL
- Refuse database mutations
- Refuse schema-destructive commands
- Refuse unrestricted raw database access
- Refuse unsupported question types outside the bounded MVP tool set
- Return an explanation if SQL fails validation
- Do not execute unsafe SQL
- Do not let resume matching widen SQL scope or expose raw profile browsing

## 10. Success Criteria

- 5 core demo questions pass
- 5 safety/refusal questions pass
- Generated SQL is visible to the user for SQL-capable responses
- Dangerous SQL is refused
- Chart spec works for job count by city
- Resume-matching requests can be routed safely when `user_id` is provided
- Light small-talk requests return safe, bounded responses
- ETL/crawler is not touched
- `clean_jobs` is the only queried table in MVP

## 11. Non-Goals

- No write SQL
- No database mutations
- No crawler control
- No automatic ETL triggering
- No multi-agent orchestration
- No unrestricted schema access
- No raw HTML querying
- No frontend dashboard yet
- No broad ETL/crawler changes
- No raw resume/profile browsing through SQL
- No semantic-search-first public behavior in MVP
- No broad open-ended chat assistant behavior

## 12. Future Capabilities

- Expand beyond `clean_jobs` after MVP contracts are stable
- Support richer charting and deeper analytics workflows
- Add semantic search as a later bounded tool or product mode
- Add more user-scoped tools beyond resume matching
- Add provider fallback or provider specialization if reliability or quality requires it

Resume matching is part of the MVP tool set, but it must stay explicitly bounded and must not widen SQL table access.

## 13. Open Questions

- What replaceable persistent memory backend should back `session_id` during MVP?
- What concrete LangChain-native model configuration should the agent use first for the ReAct/tool-routing flow?
- What level of audit and trace logging is required for internal/demo MVP operation beyond the currently approved baseline?
