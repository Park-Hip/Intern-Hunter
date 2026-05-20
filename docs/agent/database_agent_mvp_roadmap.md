# Database Agent MVP Roadmap

## Current State
InternHunter already has the core platform pieces that the database-agent MVP can build on: a FastAPI app, SQLAlchemy session management, `clean_jobs` as the product-facing structured table, existing LLM provider infrastructure, and existing search/resume APIs. For this agent specifically, the implementation direction is to use a LangChain-native provider path and a bounded ReAct-style tool-routing flow rather than a SQL-only assistant. The current public API lives in `src/internhunter/api/app.py` and now mounts both the demo routes and `POST /agent/ask`. Storage boundaries are already clear: ORM models and sessions live under `src/internhunter/storage/`, ETL persistence logic lives in `src/internhunter/storage/repositories/etl.py`, and search logic lives in `src/internhunter/search/repository.py`. The approved MVP stance is SQL-first but bounded multi-tool, with light small-talk support and guarded resume matching behind the same endpoint.

What is already decided:
- MVP query scope is `clean_jobs` only.
- `raw_jobs` must remain internal ETL evidence and must not be exposed to the agent.
- The first SQL contract is intentionally narrow: single-table, single-statement `SELECT` only.
- SQL must be validated before execution.
- Unsafe or unsupported requests must be refused.
- The public MVP shape is centered on one endpoint: `POST /agent/ask`.
- Generated SQL must be visible to the user.
- Chart output is spec-only, not rendered charts.
- The database agent should use a LangChain-native provider path.
- The database agent should use a bounded ReAct-style tool-routing flow.
- The first ReAct loop should stay bounded to 2-3 tool steps and should not depend on a separate visible intent router.
- `session_id` stays in MVP with persistent follow-up context, while the concrete backend remains deferred.
- `user_id` is not required by the SQL/query path, but it is required for resume-matching tool use.
- Resume matching is in scope as an internal tool path behind `POST /agent/ask`.
- Small-talk support is intentionally light and remains inside the same endpoint and response envelope.
- Chart generation is result-driven from executed SQL/table results only.
- The first provider stance is single-provider-first, with fallback-provider logic deferred.
- Existing search and resume APIs remain unchanged.

What is still missing:
- Agent scaffolding exists under `src/agents/`, but real SQL generation/execution and resume-tool execution are still missing.
- No SQL validator or query executor exists for the agent flow.
- No session-memory implementation exists yet for `session_id`.
- No production-grade tool-routing implementation exists yet for choosing between SQL/query, chart follow-up, and resume matching.
- No resume-tool adapter exists yet for bounded resume-matching access through the agent.
- No end-to-end ask flow with real SQL or resume execution exists yet.
- No agent-specific tests exist yet beyond the current guardrail, contract, route, and integration scaffold coverage.
- The agent docs now define intended contracts, but most of them are still planning documents rather than implemented behavior.

What is frozen by `AGENTS.md`:
- ETL/crawler design and logic
- TopCV selectors and crawl behavior
- `raw_jobs` / `clean_jobs` schema unless a justified exception is explicitly surfaced
- JobProcessor contract
- LLM validation behavior in the ETL pipeline
- Existing search API
- Existing resume matching API
- ETL orchestration

## MVP Definition
Finished MVP means the repository can accept an English question through one agent endpoint, route it through a bounded ReAct-style tool layer, produce SQL within the documented `clean_jobs` scope when the SQL tool is selected, validate that SQL against a strict allowlist, execute only validated read-only SQL, return structured tables, optionally return a short summary and chart spec, support bounded resume-matching requests, show generated SQL when SQL is used, and safely refuse requests that are dangerous or outside the MVP contract.

Required MVP capabilities:
- Turn English questions into SQL for approved `clean_jobs` fields.
- Validate SQL before execution.
- Enforce single-table `clean_jobs` scope only.
- Enforce read-only behavior.
- Apply the documented default `LIMIT` policy.
- Return tabular results in a stable response shape.
- Return visible SQL artifacts.
- Support preview-only behavior.
- Return Vega-Lite-compatible chart specs for chartable questions.
- Route requests between the SQL/query path, chart-follow-up path, and resume-matching path.
- Handle light small-talk requests safely through the same endpoint without widening into a broad assistant.
- Support resume matching through the agent when `user_id` is provided.
- Return safe refusals for unsafe or unsupported questions.
- Support persistent short follow-up context through `session_id`.
- Keep `session_id` separate from resume-specific `user_id`.
- Keep `user_id` from changing SQL scope or permissions in MVP.

Explicitly out of scope for MVP:
- Public raw SQL submission
- `raw_jobs` access
- ETL/crawler redesign
- Schema expansion beyond what is already approved
- Multi-table SQL
- joins, CTEs, subqueries, and free-text SQL matching
- Semantic search as part of the public agent flow
- Rendered charts or dashboards
- Authenticated user identity
- Rate limiting hardening
- Multi-agent orchestration

## Roadmap Principles
- [ ] Keep the implementation isolated from frozen ETL/crawler areas.
- [ ] Treat `docs/agent/sql_contract.md` as the behavioral safety center for MVP.
- [ ] Prefer bounded tool routing and narrow, explicit, highly testable SQL behavior over broad intelligence.
- [ ] Keep the first ReAct loop bounded to 2-3 tool steps and avoid a separate visible intent-router subsystem.
- [ ] Keep the public HTTP surface to one endpoint until MVP is stable.
- [ ] Reuse the existing FastAPI app, SQLAlchemy session layer, and existing LLM infrastructure where helpful, while making the agent's tool-routing path LangChain-native.
- [ ] Refuse unsupported behavior instead of adding risky fallback logic.
- [ ] Keep `clean_jobs` as the only product-facing query table.
- [ ] Keep resume matching bounded to the existing user-scoped capability and never let it widen SQL scope.
- [ ] Make every phase exit on tests and docs, not code completion alone.

## Phase 1: Contract Lock And Scope Confirmation
- Purpose
  - Convert the current planning state into an implementation-safe starting point.
  - Confirm the exact MVP boundaries before code depends on assumptions.
- Dependencies
  - Current agent docs
  - `AGENTS.md`
  - Current FastAPI and storage boundaries
- Checklist
  - [x] Reconfirm that MVP query scope is `clean_jobs` only and document that this is non-negotiable for the first slice.
  - [x] Reconfirm that `raw_jobs` remains internal ETL evidence and is never agent-queryable.
  - [x] Reconfirm the exact SQL shape allowed in MVP: single `SELECT`, single table, no joins, no CTEs, no subqueries, no free-text SQL matching.
  - [x] Reconfirm the initial approved `clean_jobs` column whitelist from `docs/agent/data_dictionary.md` and `docs/agent/sql_contract.md`.
  - [x] Reconcile any drift between `vision.md`, `sql_contract.md`, `api_contract.md`, and `data_dictionary.md`.
  - [x] Record any contract ambiguity that would block implementation and resolve it before Phase 2 starts.
  - [x] Confirm whether `company` is now considered part of the approved MVP SQL surface everywhere in the docs.
  - [x] Confirm that `session_id` support stays in the first shipped slice with persistent follow-up context.
  - [x] Confirm that `user_id` stays separate from SQL/query scope and may be used by user-scoped tools.
- Exit Criteria
  - [x] The MVP scope is stable enough that implementation can begin without hidden table-scope or SQL-scope ambiguity.
  - [x] Any blocking contract mismatch across agent docs is resolved or explicitly deferred.

## Phase 2: Decision Closure For MVP-Seam Choices
- Purpose
  - Close the implementation decisions that are still open in the docs so later phases do not stall.
- Dependencies
  - Phase 1 scope confirmation
- Checklist
  - [x] Use a bounded ReAct-style agent that can decide when to use the SQL/query tool, resume-matching tool, chart-follow-up behavior, or light small-talk handling.
  - [ ] Investigate the concrete LangChain-native model configuration later through internet research and A/B testing.
  - [x] Keep `session_id` memory in the first release.
  - [x] Keep persistent session memory behind a replaceable seam; `Mem0` is a current candidate but not yet locked.
  - [x] Use a narrower explicit SQL contract-enforcer for MVP rather than parser-backed validation on day one.
  - [x] Do not introduce a separate visible intent router in the first MVP architecture.
  - [x] Keep the first ReAct/tool-routing loop capped at 2-3 tool steps.
  - [x] Start with direct NL-to-SQL for the SQL path rather than requiring an intermediate structured intent layer.
  - [x] Keep chart generation result-driven from executed SQL/table results while allowing chart intent inference only for routing and chart-request handling.
  - [x] Keep summary generation deterministic-first or hybrid, grounded in executed results.
  - [x] Keep chart generation deterministic-first or hybrid from normalized result tables rather than a separate free-form LLM path.
  - [x] Decide whether summary generation is always on by default or only controlled by `include_summary`.
  - [x] Decide how much SQL visibility is exposed in normal mode versus `debug=true`.
  - [x] Decide the refusal taxonomy that will be surfaced through the API response.
  - [x] Decide the first timeout stance for generation, validation, and execution.
  - [x] Decide the MVP stance on trace IDs and structured logging fields.
  - [x] Start with a single provider configuration first and defer fallback-provider logic.
- Exit Criteria
  - [x] All decisions that would block architecture or API implementation are explicitly chosen and documented.
  - [x] Remaining open questions are clearly marked as post-MVP or later hardening work.

## Phase 3: Architecture And Runtime Plan Finalization
- Purpose
  - Translate the contract decisions into a concrete runtime blueprint aligned with the current repository layout.
- Dependencies
  - Phase 1
  - Phase 2
- Checklist
    - [x] Finalize the runtime component split across `src/internhunter/api/routes/agent.py`, `src/agents/`, and `src/services/query/`.
    - [x] Define the bounded tool seam for resume matching without modifying the existing resume API contract.
    - [x] Define the tool-routing contract for choosing SQL/query, chart follow-up, resume matching, or refusal.
    - [x] Define the internal ask-flow artifact sequence: request, schema context, SQL candidate, validation result, execution result, table result, summary result, chart result, final response.
    - [x] Define how the new agent route plugs into `src/internhunter/api/app.py` without changing existing routes.
    - [x] Define how the agent flow reuses `SessionLocal` and existing ORM models without depending on ETL repositories.
    - [x] Define how the query execution layer stays separate from HTTP and from LLM prompt logic.
    - [x] Define the session-memory seam so it can start minimal and be replaced later.
    - [x] Define where safe refusal mapping lives and where raw validator outcomes are translated for users.
    - [x] Define the logging seam so request lifecycle events can be observed without overlogging.
- Exit Criteria
  - [x] `architecture.md` is complete enough that implementation teams can work in parallel without guessing boundaries.
  - [x] The intended module placement matches the current codebase structure.

## Phase 4: SQL Safety Contract Finalization
- Purpose
  - Lock the exact SQL behavior before any execution path is built.
- Dependencies
  - Phase 1
  - Phase 2
  - Phase 3
- Checklist
    - [x] Finalize the allowed SQL grammar for MVP in executable terms.
    - [x] Finalize the single-table whitelist for `clean_jobs`.
    - [x] Finalize the column whitelist and the blocked-column list.
    - [x] Finalize the default `LIMIT` insertion rule.
    - [x] Finalize maximum limit values for row-returning and grouped/chart queries.
    - [x] Finalize the refusal behavior for excessive limits.
    - [x] Finalize whether `ORDER BY` on aggregate aliases is allowed and how it is validated.
  - [x] Defer grouped analytics over `domain_knowledge`; do not allow it in grouped/chart outputs for MVP.
  - [x] Finalize whether array/JSON fields such as `cities` and `tech_stack` are queryable only through constrained patterns or through a narrower abstraction layer.
  - [x] Finalize the exact handling of `SELECT *`, trailing semicolons, whitespace normalization, and multi-statement detection.
  - [x] Finalize the machine-readable validator categories that tests will assert on.
- Exit Criteria
  - [x] `sql_contract.md` is precise enough to directly drive validator unit tests.
  - [x] No core validator rule remains implicit.

## Phase 5: API Contract Finalization
- Purpose
  - Make the single public endpoint stable before implementation begins.
- Dependencies
  - Phase 2
  - Phase 3
  - Phase 4
- Checklist
    - [x] Confirm `POST /agent/ask` as the only public MVP endpoint.
    - [x] Finalize request fields and defaults.
    - [x] Finalize which fields are always present in the response envelope.
    - [x] Finalize SQL visibility rules for normal, preview, refusal, and debug modes.
    - [x] Finalize the table payload shape and empty-result behavior.
    - [x] Finalize the chart payload shape and omission warnings.
    - [x] Finalize refusal response semantics and error codes.
    - [x] Finalize `200` versus `400` versus `500` behavior.
    - [x] Finalize whether preview responses always include both `model_generated_sql` and `validated_sql`.
    - [x] Finalize whether `session_id` is echoed back in metadata.
- Exit Criteria
    - [x] `api_contract.md` is stable enough to drive Pydantic models and integration tests.
    - [x] No public wire-format ambiguity remains for MVP.

## Phase 6: Security And Refusal Model Finalization
- Purpose
  - Ensure the MVP has a documented guardrail story before execution is enabled.
- Dependencies
  - Phase 4
  - Phase 5
- Checklist
    - [x] Finalize the minimum prompt-injection stance for MVP.
    - [x] Finalize the rule that user input, session context, and model output are all untrusted.
  - [x] Finalize the refusal posture for requests that try to access blocked tables, blocked columns, or blocked query shapes.
  - [x] Finalize the logging stance for generated SQL in internal/demo MVP.
  - [x] Finalize safe debug behavior so it never exposes secrets or raw stack traces.
  - [x] Finalize the timeout policy that prevents runaway generation or execution.
  - [x] Finalize the minimum audit/logging expectations required for debugging and demo confidence.
- Exit Criteria
  - [x] `security_model.md` clearly states the MVP trust boundaries and refusal rules.
  - [x] The implementation team can build without inventing security behavior ad hoc.

## Phase 7: Queryable Data-Scope Readiness
- Purpose
  - Confirm that the runtime query surface in `clean_jobs` is practical and documented before the agent layer is implemented.
- Dependencies
  - Phase 1
  - Phase 4
- Checklist
  - [ ] Verify the actual live ORM fields in `CleanJobDB` against the agent data dictionary.
    - [x] Verify the SQL-facing status of array/JSON fields such as `cities`, `tech_stack`, `technical_competencies`, and `domain_knowledge`.
    - [x] Verify that blocked long-text fields remain documented as non-queryable in MVP SQL.
  - [ ] Verify that default display fields are aligned with the API contract and SQL contract.
    - [x] Define the exact city normalization expectation that the agent may rely on during SQL generation.
  - [x] Keep `domain_knowledge` out of grouped/chart outputs for MVP.
  - [ ] Confirm whether any additional schema inspection helper is needed to avoid hardcoding unstable assumptions.
- Exit Criteria
  - [ ] The queryable `clean_jobs` surface is documented, stable, and narrow enough for implementation.
  - [ ] No hidden data-shape blocker remains for the bounded SQL/query MVP surface.

## Phase 8: Agent Orchestration Implementation
- Purpose
  - Build the core ask-flow orchestration behind the new endpoint.
- Dependencies
  - Phases 3 through 7
- Checklist
  - [ ] Add the new agent route module under `src/internhunter/api/routes/`.
  - [ ] Add the core orchestration service under `src/agents/`.
  - [ ] Add schema/context assembly for approved `clean_jobs` fields only.
  - [ ] Add LangChain-native provider invocation for tool routing and SQL generation using the later-selected MVP model configuration.
  - [ ] Add handling for preview, refusal, SQL execution, resume-matching, summary, and chart branches.
  - [ ] Add `user_id` handling for resume-matching requests and explicit refusal when that tool path is selected without `user_id`.
  - [ ] Prove through the orchestration boundary that resume-tool use does not widen SQL table scope or SQL permissions.
  - [ ] Add persistent session-context support in MVP.
  - [ ] Keep orchestration logic out of the route layer and out of storage repositories.
  - [ ] Add structured logging at the orchestration seam.
- Exit Criteria
  - [ ] The agent ask flow exists end-to-end behind an internal service boundary.
  - [ ] The route remains thin and only maps request/response behavior.

## Phase 9: SQL Validator Implementation
- Purpose
  - Implement the strict execution gate that enforces the contract.
- Dependencies
  - Phase 4
  - Phase 8
- Checklist
  - [ ] Implement single-statement enforcement.
  - [ ] Implement non-`SELECT` rejection.
  - [ ] Implement blocked-shape rejection for joins, CTEs, subqueries, set operations, and wildcard selects.
  - [ ] Implement table whitelist enforcement for `clean_jobs` only.
  - [ ] Implement column whitelist enforcement.
  - [ ] Implement long-text-field rejection.
  - [ ] Implement forbidden text-match rejection.
  - [ ] Implement safe normalization for whitespace, trailing semicolon removal, and default `LIMIT`.
  - [ ] Implement excessive-limit refusal behavior.
  - [ ] Return explicit validation metadata and machine-readable refusal categories.
- Exit Criteria
  - [ ] The validator can accept only contract-compliant SQL and reject everything else needed for MVP.
  - [ ] The validator is independently unit-testable without running the full agent flow.

## Phase 10: Read-Only Query Execution Layer
- Purpose
  - Execute only validated SQL and normalize results into the API table shape.
- Dependencies
  - Phase 8
  - Phase 9
- Checklist
  - [ ] Add a read-only query execution service under `src/services/query/`.
  - [ ] Ensure the executor accepts validated SQL only.
  - [ ] Reuse `SessionLocal` and existing DB connection handling.
  - [ ] Add result normalization into a consistent table artifact.
  - [ ] Preserve exact `executed_sql` visibility in the response path.
  - [ ] Add graceful handling for empty results.
  - [ ] Add bounded execution-time behavior consistent with the chosen timeout stance.
- Exit Criteria
  - [ ] Validated SQL can execute against `clean_jobs` and return normalized table output.
  - [ ] Unsafe SQL still cannot bypass the validator.

## Phase 11: Summary And Chart Output Layer
- Purpose
  - Add the user-facing output behavior that turns query results into a usable MVP experience.
- Dependencies
  - Phase 8
  - Phase 10
- Checklist
  - [ ] Add short result-summary generation grounded in the validated result table.
  - [ ] Add preview-only summary behavior that clearly states execution was skipped.
  - [ ] Add refusal-summary behavior that explains the block safely.
  - [ ] Add chart suitability checks for grouped/chartable results only.
  - [ ] Add Vega-Lite-compatible chart-spec generation.
  - [ ] Add omission warnings for non-chartable results.
  - [ ] Ensure chart generation never creates a second execution path.
- Exit Criteria
  - [ ] Successful grouped questions can return usable chart specs.
  - [ ] Non-chartable questions fail gracefully without unsafe fallback behavior.

## Phase 12: Session Follow-Up Support
- Purpose
  - Deliver the minimal session behavior promised by the MVP docs without overdesigning memory.
- Dependencies
  - Phase 2
  - Phase 8
- Checklist
  - [ ] Implement the chosen MVP session-memory approach.
  - [ ] Keep memory bounded to short follow-up context, not long unfiltered transcripts.
  - [ ] Support the documented follow-up patterns such as narrowing the previous result set or requesting a chart from the prior result.
  - [ ] Ensure session context is treated as untrusted input.
  - [ ] Add a clear fallback path when no prior context exists for a supplied `session_id`.
- Exit Criteria
  - [ ] Same-session follow-up behavior works for the minimum documented cases.
  - [ ] Memory does not silently widen agent scope or bypass validation.

## Phase 13: API Integration And App Wiring
- Purpose
  - Expose the finished MVP flow through the current FastAPI app without disturbing existing APIs.
- Dependencies
  - Phases 8 through 12
- Checklist
  - [ ] Register the new agent router in `src/internhunter/api/app.py`.
  - [ ] Keep existing `demo_routes.py` behavior unchanged.
  - [ ] Add request/response Pydantic models for the agent API contract.
  - [ ] Add consistent HTTP status behavior for success, refusal, request validation errors, and unexpected server failures.
  - [ ] Ensure root and health endpoints remain unaffected.
- Exit Criteria
  - [ ] The FastAPI app exposes the new agent endpoint and existing endpoints still behave as before.

## Phase 14: Test And Verification Build-Out
- Purpose
  - Build the test safety net required by `AGENTS.md` before MVP signoff.
- Dependencies
  - Phases 8 through 13
- Checklist
  - [ ] Add validator unit tests for safe `SELECT` acceptance.
  - [ ] Add validator unit tests for write/admin SQL rejection.
  - [ ] Add validator unit tests for multi-statement rejection.
  - [ ] Add validator unit tests for unknown-table rejection.
  - [ ] Add validator unit tests for non-whitelisted-column rejection.
  - [ ] Add validator unit tests for missing-limit handling.
  - [ ] Add validator unit tests for excessive-limit refusal.
  - [ ] Add unit tests for table formatting behavior.
  - [ ] Add unit tests for refusal mapping behavior.
  - [ ] Add unit tests for chart suitability and chart-spec output.
  - [ ] Add unit tests for tool routing and resume-tool adaptation behavior.
  - [ ] Add unit tests for session-context assembly if session support remains in MVP.
  - [ ] Add integration tests for `POST /agent/ask` happy path.
  - [ ] Add integration tests for preview-only flow.
  - [ ] Add integration tests for refusal flow.
  - [ ] Add integration tests for chart-included flow.
  - [ ] Add integration tests for resume-matching flow.
  - [ ] Add integration tests for same-session follow-up flow if session support remains in MVP.
  - [ ] Add contract-level assertions for response-envelope consistency.
- Exit Criteria
  - [ ] The MVP has focused unit and integration tests covering both happy-path and safety-path behavior.
  - [ ] The evaluation set can be traced to concrete automated tests.

## Phase 15: Documentation Sync And MVP Readiness Review
- Purpose
  - Bring the docs into “implemented MVP” alignment and perform the final readiness gate.
- Dependencies
  - All earlier phases
- Checklist
  - [ ] Update all agent planning docs to reflect the final shipped behavior rather than intended behavior.
  - [ ] Update `docs/README.md` if new agent docs or usage notes need to be highlighted.
  - [ ] Add lightweight usage documentation for local agent testing if needed.
  - [ ] Confirm that no frozen ETL/crawler docs were rewritten unnecessarily.
  - [ ] Run the smallest relevant test suite for the shipped scope and capture exact commands/results.
  - [ ] Verify the core demo questions and safety/refusal questions manually or through tests.
  - [ ] Review logs for safe behavior and useful debugging signals.
  - [ ] Confirm the final response contract, SQL contract, and data dictionary still agree.
- Exit Criteria
  - [ ] The docs describe the shipped MVP accurately.
  - [ ] The project has a clear evidence-based basis for declaring MVP complete.

## Cross-Cutting Decisions
Must decide before implementation:
- [x] Use a bounded ReAct/tool-routing layer rather than direct NL-to-SQL only.
- [ ] Concrete LangChain-native model configuration, to be chosen later through research and A/B testing.
- [x] Validator approach: narrower explicit validator for MVP.
- [ ] Exact persistent session-memory storage choice for MVP; `Mem0` is a current candidate, but the seam should stay replaceable.
- [x] No separate visible intent router in the first MVP architecture.
- [x] Keep the first ReAct loop capped at 2-3 tool steps.
- [x] Use direct NL-to-SQL first for the SQL path.
- [x] Refusal taxonomy and machine-readable error categories.
- [x] SQL visibility policy for normal versus debug responses.
- [x] Exact limit policy behavior, including grouped-query max limit.
- [x] Limit MVP chart output to a small Vega-Lite-compatible set such as `bar` and `line`.

Should decide soon:
- [x] Whether summary generation is always on by default.
- [x] Whether chart generation is inferred automatically in addition to `include_chart=true`.
- [x] Keep summary generation deterministic-first or hybrid and grounded in executed results.
- [x] Keep chart generation deterministic-first or hybrid from normalized results.
- [x] Keep `domain_knowledge` out of grouped outputs.
- [x] Whether trace IDs are emitted by default.
- [x] Log `validated_sql` and `executed_sql` by default, and log raw `model_generated_sql` only in debug or refusal-analysis paths.
- [x] Whether preview mode is part of the first shipping slice or a near-immediate follow-up slice.
- [x] Start with a single provider configuration and defer fallback-provider logic.

Can defer:
- [ ] Richer session memory beyond short same-session follow-ups.
- [ ] Semantic search integration into the agent flow.
- [ ] Expanded analytics over long-text fields.
- [ ] Additional chart types or chart editing workflows.
- [ ] Caching and performance optimization beyond basic timeouts.

Out of scope for MVP:
- [ ] Authenticated user identity.
- [ ] Rate limiting hardening.
- [ ] Multi-agent orchestration.
- [ ] Public raw SQL endpoints.
- [ ] Access to `raw_jobs`, audit tables, or operational tables.
- [ ] ETL/crawler redesign.
- [ ] Frontend dashboard rendering.

## Documentation Plan
- [x] Keep `docs/agent/vision.md` aligned with the actual first-shipped scope, especially around session support and the bounded SQL-contract constraint.
- [ ] Complete `docs/agent/architecture.md` as the final runtime blueprint rather than a future-only plan.
- [x] Treat `docs/agent/sql_contract.md` as the implementation source of truth for validator behavior and keep it exact.
- [x] Finalize `docs/agent/api_contract.md` before route implementation depends on unstated assumptions.
- [x] Finalize `docs/agent/security_model.md` before enabling execution in non-preview mode.
- [x] Keep `docs/agent/data_dictionary.md` aligned with the actual queryable `clean_jobs` surface.
- [x] Expand `docs/agent/eval_set.md` into a concrete regression checklist tied to automated tests.
- [x] Keep the roadmap aligned with the approved bounded multi-tool MVP defaults, including light small-talk, guarded resume matching, result-driven charting, and deferred fallback-provider logic.
- [x] Do not add new agent docs in this pass; defer any `tool_contracts.md` or `memory_contract.md` work until the later agent-specific design phase.
- [ ] Update `docs/README.md` only if the new agent subsystem changes how contributors should navigate the docs.
- [ ] Add a lightweight local-testing note only if needed for agent-specific manual verification.
- [ ] Avoid broad rewrites of current-system or ETL docs unless the agent work truly changes their documented behavior.

## Risks And Mitigations
- [ ] Risk: SQL safety scope drifts wider during implementation.
  Mitigation: lock `sql_contract.md` first and require validator tests before endpoint wiring.
- [ ] Risk: Session support adds too much complexity too early.
  Mitigation: keep memory bounded and replaceable, require only the smallest persistent follow-up behavior for MVP, and defer vendor locking.
- [ ] Risk: JSON/array fields in `clean_jobs` create ambiguous SQL patterns.
  Mitigation: define supported filter/group patterns explicitly before validator implementation.
- [ ] Risk: Placeholder-like planning language is mistaken for shipped behavior.
  Mitigation: convert critical docs to implementation-ready contracts before coding.
- [ ] Risk: Existing search or resume APIs are accidentally coupled into the agent flow.
  Mitigation: keep the new subsystem isolated under new route/service modules and do not modify existing endpoints.
- [ ] Risk: The agent selects the wrong tool for a request.
  Mitigation: keep tool-routing rules explicit, test routing decisions directly, and prefer safe refusal over ambiguous routing.
- [ ] Risk: Resume-tool use accidentally widens SQL scope or behaves like profile browsing.
  Mitigation: keep `user_id` out of SQL scope decisions, enforce bounded resume-tool inputs/outputs, and add explicit refusal tests.
- [ ] Risk: Long-text or semantic search requests pressure the MVP into unsupported fallback logic.
  Mitigation: prefer explicit refusal and document semantic search as post-MVP.
- [ ] Risk: Result size or execution time becomes unbounded.
  Mitigation: enforce default limits, max limits, and execution timeouts in the validator/executor path.
- [ ] Risk: Logging leaks too much internal detail.
  Mitigation: finalize the logging policy in the security model before enabling debug behavior.
- [ ] Risk: Persistent memory is required, but the concrete storage choice is still undecided.
  Mitigation: keep a replaceable memory seam, document `Mem0` only as a candidate, and defer vendor locking until later evaluation.
- [ ] Risk: Documentation and implementation drift.
  Mitigation: require doc updates in the same phase as each contract or subsystem change.

## MVP Acceptance Checklist
- [ ] The app exposes `POST /agent/ask` and existing APIs still work unchanged.
- [ ] The agent accepts English natural-language questions only.
- [ ] The agent selects the correct bounded tool path or safely refuses when the request is ambiguous or unsupported.
- [ ] The agent generates SQL only within the documented `clean_jobs` MVP scope.
- [ ] All generated SQL is validated before execution.
- [ ] Unsafe, unsupported, or out-of-scope requests are refused and not executed.
- [ ] The validator enforces single-table `clean_jobs` queries only.
- [ ] The validator blocks writes, schema changes, joins, CTEs, subqueries, multi-statement SQL, wildcard selects, and blocked columns.
- [ ] Queries without `LIMIT` receive the documented safe default limit.
- [ ] Excessive limits are refused according to the documented policy.
- [ ] Successful executed responses return visible SQL, a normalized table payload, and stable metadata.
- [ ] Preview-only responses validate SQL and skip execution cleanly.
- [ ] Chartable grouped questions can return a Vega-Lite-compatible chart spec.
- [ ] Resume-matching requests with `user_id` can return bounded match results through the same endpoint.
- [ ] Resume-matching requests without `user_id` are refused safely.
- [ ] `user_id` does not change SQL scope, SQL permissions, or table exposure.
- [ ] `domain_knowledge` is not used as a grouped or chart dimension in MVP outputs.
- [ ] Non-chartable results omit charts safely with warnings when appropriate.
- [ ] The core demo questions pass.
- [ ] The core refusal/safety questions pass.
- [ ] Focused unit tests exist for SQL safety behavior.
- [ ] Integration tests exist for the end-to-end agent API flow.
- [ ] Agent docs are updated to reflect shipped behavior rather than future intent.
- [ ] No ETL/crawler redesign was introduced to deliver the MVP.
- [ ] `raw_jobs` remains internal ETL evidence and is not exposed to the agent.
