# Database-Agent Wave 1 Implementation Plan

This document turns the approved first coding wave into a tracked execution checklist for the database-agent MVP.

## Implementation Objective

Deliver the first end-to-end coding wave of the database-agent MVP so the repo gains a thin `POST /agent/ask` path with bounded orchestration, mandatory SQL validation, validated read-only execution against `clean_jobs`, shared response assembly, and enough test coverage to prove the core SQL, refusal, preview, chart, resume, session, and small-talk behaviors.

## Locked Constraints

- [ ] SQL scope is `clean_jobs` only.
- [ ] `raw_jobs` must never be exposed.
- [ ] No joins, CTEs, subqueries, or public raw SQL mode.
- [ ] One public endpoint only: `POST /agent/ask`.
- [ ] Runtime flow stays fixed:
  - request -> pre-agent guardrail -> bounded ReAct/tool selection -> SQL or resume or small-talk path -> validation -> execution -> result shaping -> response
- [ ] SQL validation is mandatory.
- [ ] The executor must accept validated SQL only.
- [ ] `user_id` must not affect SQL scope or permissions.
- [ ] Resume matching is a guarded tool branch, not a second public API.
- [ ] Small-talk is intentionally narrow.
- [ ] Charting is result-driven only.
- [ ] Session memory is persistent in behavior but behind a replaceable seam.
- [ ] Provider stance is single-provider-first.
- [ ] The existing ETL/crawler, schema, search API, and resume API remain frozen.

## Proposed Build Sequence

1. [x] Contract scaffolding and internal DTO baseline
2. [ ] Route and orchestration skeleton
3. [ ] Pre-agent guardrail and bounded routing skeleton
4. [ ] SQL generation seam and provider integration boundary
5. [ ] SQL validator
6. [ ] Validated read-only executor and table normalization
7. [ ] Response assembly, refusal mapping, and preview flow
8. [ ] Summary and chart branch
9. [ ] Resume-tool branch
10. [ ] Session memory seam and follow-up behavior
11. [ ] End-to-end integration and acceptance hardening
12. [ ] Docs sync and MVP checklist closure

## Slice Details

### 1. Contract Scaffolding And Internal DTO Baseline

**Purpose**

- Turn the existing API/SQL/docs contracts into code-facing types and stable internal artifacts without implementing behavior yet.

**Scope**

- request/response models
- internal ask/request/result objects
- refusal/error category enums or equivalents
- shared table/chart/summary artifact shapes

**Key modules/boundaries involved**

- route boundary
- orchestration boundary
- query service boundary
- response assembly boundary

**Checklist**

  - [x] Add request model scaffolding for `POST /agent/ask`
  - [x] Add response envelope scaffolding for `ok`, `refused`, and preview cases
  - [x] Add internal typed artifacts for ask/request/result flow
  - [x] Add refusal/error category types
  - [x] Add shared table/chart/summary artifact types

**Tests required**

  - [x] request model validation tests
  - [x] response envelope shape tests
  - [x] serialization tests for preview/refusal/ok cases

**Definition of done**

  - [x] The codebase has stable typed objects for the public API and internal orchestration artifacts.
  - [x] No runtime behavior is implemented yet beyond model validation.
  - [x] Tests prove the contract scaffolding matches the documented envelope.

**Doc/checklist updates**

  - [x] No contract ambiguity required doc changes in this phase

### 2. Route And Orchestration Skeleton

**Purpose**

- Introduce the new endpoint and a thin orchestration seam without real tool behavior yet.

**Scope**

- register `POST /agent/ask`
- thin route calling a central agent service
- placeholder orchestration result mapping

**Key modules/boundaries involved**

- route
- orchestration
- app wiring

**Checklist**

- [x] Add the new route module
- [x] Wire the new route into the FastAPI app
- [x] Add a thin orchestration service entrypoint
- [x] Keep existing routes unchanged

**Tests required**

- [x] endpoint exists
- [x] malformed payload returns `422`
- [x] happy-path stub returns the shared envelope

**Definition of done**

- [x] The FastAPI app exposes `POST /agent/ask`.
- [x] Route logic stays thin and delegates immediately.
- [x] Existing endpoints remain unchanged.

**Doc/checklist updates**

- [x] Update roadmap checklist item for route exposure when complete

### 3. Pre-Agent Guardrail And Bounded Routing Skeleton

**Purpose**

- Add the first non-SQL decision layer so requests can be classified into small-talk, SQL-capable, resume-capable, or refusal before deeper execution.

**Scope**

- lightweight request screening
- narrow routing skeleton
- no full intent-router subsystem

**Key modules/boundaries involved**

- pre-agent guardrail
- orchestration
- response assembly

**Checklist**

- [ ] Add lightweight pre-agent request screening
- [ ] Add bounded branch selection for SQL, resume, small-talk, and refusal
- [ ] Keep the branch logic narrow and reversible

**Tests required**

- [ ] small-talk request routes to bounded conversational response
- [ ] obviously unsupported request refuses safely
- [ ] SQL-like request enters SQL-capable branch
- [ ] resume request without `user_id` can be marked for refusal

**Definition of done**

- [ ] The orchestrator can select the top-level branch safely.
- [ ] No branch can bypass refusal handling.
- [ ] Small-talk is handled without touching SQL.

**Doc/checklist updates**

- [ ] Update docs only if branch semantics differ from the approved bounded behavior

### 4. SQL Generation Seam And Provider Integration Boundary

**Purpose**

- Add the SQL-capable generation seam without yet trusting it for execution.

**Scope**

- provider invocation boundary
- SQL generation component
- prompt/context seam for approved `clean_jobs` scope
- direct NL-to-SQL first

**Key modules/boundaries involved**

- orchestration
- provider integration
- SQL generation seam

**Checklist**

- [ ] Add provider invocation seam for agent SQL generation
- [ ] Add SQL candidate generation artifact flow
- [ ] Add approved schema/context assembly for `clean_jobs`
- [ ] Keep generated SQL separate from execution

**Tests required**

- [ ] unit tests for generation interface contract
- [ ] tests proving generated SQL is captured as an artifact, not executed
- [ ] prompt/context boundary tests if feasible

**Definition of done**

- [ ] SQL-capable requests produce a SQL candidate artifact.
- [ ] Provider use is isolated behind a replaceable seam.
- [ ] No execution happens from this slice alone.

**Doc/checklist updates**

- [ ] Update docs only if provider/config or prompt boundaries force a clarification

### 5. SQL Validator

**Purpose**

- Implement the core safety gate before any real execution is allowed.

**Scope**

- single-statement enforcement
- `SELECT`-only enforcement
- `clean_jobs` table whitelist
- column whitelist
- blocked joins/CTEs/subqueries
- default `LIMIT`
- excessive-limit refusal
- wildcard/select-star refusal
- long-text/text-match refusal

**Key modules/boundaries involved**

- query services
- orchestration refusal mapping

**Checklist**

- [ ] Implement single-statement enforcement
- [ ] Implement `SELECT`-only enforcement
- [ ] Implement `clean_jobs` table whitelist enforcement
- [ ] Implement column whitelist enforcement
- [ ] Implement blocked joins/CTEs/subqueries enforcement
- [ ] Implement default `LIMIT` insertion
- [ ] Implement excessive-limit refusal
- [ ] Implement wildcard select refusal
- [ ] Implement long-text/text-match refusal
- [ ] Return explicit validation success/refusal metadata

**Tests required**

- [ ] safe `SELECT` allowed
- [ ] write/admin SQL rejected
- [ ] multi-statement rejected
- [ ] unknown table rejected
- [ ] unknown column rejected
- [ ] missing limit handled
- [ ] excessive limit refused
- [ ] joins/CTEs/subqueries rejected
- [ ] long-text filters rejected

**Definition of done**

- [ ] The validator independently enforces the documented SQL contract.
- [ ] Validation returns explicit success/refusal metadata.
- [ ] The validator can be tested without the full agent path.

**Doc/checklist updates**

- [ ] Update roadmap checklist and SQL-safety completion items

### 6. Validated Read-Only Executor And Table Normalization

**Purpose**

- Add the executor that can run only validated SQL and shape rows into the shared table artifact.

**Scope**

- validated-SQL-only executor
- DB session reuse
- normalized table output
- empty result handling

**Key modules/boundaries involved**

- query executor
- table formatter
- storage session boundary

**Checklist**

- [ ] Add validated-SQL-only executor boundary
- [ ] Reuse existing DB session handling
- [ ] Add normalized table formatter
- [ ] Add empty-result handling

**Tests required**

- [ ] executor rejects non-validated input at the boundary
- [ ] valid validated SQL produces normalized table output
- [ ] empty results return `row_count=0` and empty rows

**Definition of done**

- [ ] Executed SQL comes only from the validator output.
- [ ] Table artifacts match the API contract shape.
- [ ] SQL path can now produce real table results.

**Doc/checklist updates**

- [ ] Update roadmap executor checklist items

### 7. Response Assembly, Refusal Mapping, And Preview Flow

**Purpose**

- Stabilize outward behavior before adding richer post-processing.

**Scope**

- preview path
- refusal path
- SQL visibility rules
- metadata population
- one shared response envelope across branches

**Key modules/boundaries involved**

- orchestration
- response mapper
- refusal/error mapper

**Checklist**

- [ ] Add preview response path
- [ ] Add refusal response path
- [ ] Add SQL visibility mapping for normal/debug/preview
- [ ] Add shared metadata population
- [ ] Keep one response envelope across all branches

**Tests required**

- [ ] preview returns validated SQL and skips execution
- [ ] refusal returns `status=\"refused\"` and safe error object
- [ ] SQL visibility matches normal vs debug vs preview expectations

**Definition of done**

- [ ] SQL path and refusal path both return the documented envelope.
- [ ] Preview is safe and explicit.
- [ ] Metadata fields are populated consistently enough for downstream tests.

**Doc/checklist updates**

- [ ] Update roadmap/API checklist items if implementation confirms the contract

### 8. Summary And Chart Branch

**Purpose**

- Add the core user-facing result experience after safe SQL execution exists.

**Scope**

- deterministic-first or hybrid summary generation
- result-driven chart suitability checks
- Vega-Lite spec generation
- chart omission warnings

**Key modules/boundaries involved**

- summary component
- chart component
- response assembly

**Checklist**

- [ ] Add result-grounded summary generation
- [ ] Add result-driven chart suitability checks
- [ ] Add Vega-Lite-compatible chart spec generation
- [ ] Add chart omission warnings

**Tests required**

- [ ] grouped result can produce chart spec
- [ ] non-chartable result returns warning and no chart
- [ ] summary remains grounded in result data
- [ ] preview does not fabricate chart output from unexecuted SQL

**Definition of done**

- [ ] Chart output comes only from executed normalized table results.
- [ ] Summary output is stable and bounded.
- [ ] No second execution path appears through charting.

**Doc/checklist updates**

- [ ] Update roadmap checklist items for summary/chart behavior

### 9. Resume-Tool Branch

**Purpose**

- Add the guarded non-SQL user-scoped tool branch without changing the existing resume subsystem.

**Scope**

- adapter around existing resume matching capability
- `user_id` requirement handling
- normalized match-result response in the shared envelope

**Key modules/boundaries involved**

- orchestration
- resume-tool adapter
- response assembly

**Checklist**

- [ ] Add adapter around existing resume matching capability
- [ ] Add `user_id` requirement handling
- [ ] Add normalized resume-match response assembly
- [ ] Keep resume branch independent from SQL scope

**Tests required**

- [ ] resume request with `user_id` succeeds
- [ ] resume request without `user_id` refuses safely
- [ ] resume path does not generate or execute SQL
- [ ] `user_id` does not affect SQL branch behavior

**Definition of done**

- [ ] Resume matching works through the agent entrypoint as a guarded branch.
- [ ] Existing resume API remains untouched.
- [ ] SQL scope remains unchanged.

**Doc/checklist updates**

- [ ] Update roadmap checklist for resume-tool branch completion

### 10. Session Memory Seam And Follow-Up Behavior

**Purpose**

- Add the promised follow-up behavior without overdesigning memory internals.

**Scope**

- replaceable persistent memory interface
- first backend choice
- bounded follow-up context
- session-aware chart and narrowing follow-ups

**Key modules/boundaries involved**

- memory seam
- orchestration
- SQL/resume branch reuse

**Checklist**

- [ ] Add replaceable persistent memory interface
- [ ] Choose and wire the first backend
- [ ] Add bounded follow-up context handling
- [ ] Support chart and narrowing follow-up cases
- [ ] Add safe fallback for missing or unknown `session_id`

**Tests required**

- [ ] same-session narrowing query works
- [ ] same-session chart follow-up works
- [ ] missing or unknown `session_id` falls back safely
- [ ] session context is treated as untrusted

**Definition of done**

- [ ] The minimum documented follow-up cases pass.
- [ ] Memory remains behind a replaceable seam.
- [ ] No identity or authorization semantics leak into `session_id`.

**Doc/checklist updates**

- [ ] Update roadmap/memory checklist once the first backend and seam are real

### 11. End-To-End Integration And Acceptance Hardening

**Purpose**

- Turn the assembled slices into a credible MVP coding wave with evidence.

**Scope**

- end-to-end integration coverage
- acceptance cases from the eval set
- logging/tracing sanity checks where practical

**Key modules/boundaries involved**

- full route/orchestrator/query path
- resume path
- memory path

**Checklist**

- [ ] Add end-to-end happy-path coverage
- [ ] Add end-to-end refusal coverage
- [ ] Add end-to-end preview coverage
- [ ] Add end-to-end chart coverage
- [ ] Add end-to-end resume coverage
- [ ] Add end-to-end session follow-up coverage
- [ ] Add end-to-end small-talk coverage
- [ ] Add basic observability sanity assertions where practical

**Tests required**

- [ ] core NL-to-SQL happy paths
- [ ] refusal paths
- [ ] preview path
- [ ] chart path
- [ ] resume path
- [ ] session follow-up path
- [ ] small-talk path

**Definition of done**

- [ ] The eval-set minimum cases are represented in automated tests.
- [ ] The first coding wave has evidence beyond unit tests alone.

**Doc/checklist updates**

- [ ] Update roadmap acceptance checklist items that now have implementation proof

### 12. Docs Sync And MVP Checklist Closure

**Purpose**

- Ensure the implemented first wave and the planning docs stay aligned.

**Scope**

- update planning docs where behavior became explicit
- update roadmap checklist items
- update any local testing notes if added

**Key modules/boundaries involved**

- docs only

**Checklist**

- [ ] Update planning docs to match implemented first-wave behavior
- [ ] Update roadmap checkboxes
- [ ] Update any local testing notes if needed
- [ ] Re-read key agent docs for consistency

**Tests required**

- [ ] No code tests required beyond re-reading docs against implemented behavior

**Definition of done**

- [ ] The docs describe the actual first wave accurately.
- [ ] No stale planning wording contradicts the shipped behavior of this wave.

**Doc/checklist updates**

- [ ] roadmap checkboxes
- [ ] any agent doc sections that moved from planned to implemented behavior

## Testing Strategy Across Slices

- [ ] Start with contract/model tests first so later slices build against fixed request/response shapes.
- [ ] Treat the SQL validator as the most heavily unit-tested subsystem.
- [ ] Add API integration tests as soon as the route and orchestration skeleton exist, then keep extending them slice-by-slice.
- [ ] Keep one growing acceptance layer tied directly to `docs/agent/eval_set.md`.
- [ ] Ensure minimum cross-slice coverage includes:
  - SQL validator behavior
  - refusal behavior
  - preview behavior
  - normalized table output
  - result-driven chart behavior
  - guarded resume-tool behavior
  - session follow-up behavior
  - light small-talk behavior
- [ ] Prefer the smallest relevant test command set per slice, but require real passing evidence before moving on.

## Risks During Implementation

- [ ] Routing complexity grows too early
  - Containment: keep the first routing skeleton minimal and bounded; prefer refusal over clever branching.
- [ ] SQL generation and validation get coupled
  - Containment: keep the validator independently testable and mandatory before execution.
- [ ] Resume path starts acting like a broader user-data tool
  - Containment: keep `user_id` logic isolated to the adapter and refusal checks.
- [ ] Memory design expands beyond MVP
  - Containment: implement only the documented follow-up cases; keep the backend replaceable.
- [ ] Charting becomes a second reasoning path
  - Containment: generate charts only from executed normalized table results.
- [ ] Provider/tool orchestration details delay the first coding wave
  - Containment: keep single-provider-first and direct NL-to-SQL first; defer richer provider decisions.
- [ ] Docs drift while code lands
  - Containment: attach doc/checklist updates to the end of each relevant slice, not only at the very end.

## Deferred Items

- [ ] Provider fallback logic
- [ ] Richer chart families and chart editing
- [ ] Semantic-search integration
- [ ] Broader schema access beyond `clean_jobs`
- [ ] Parser-backed SQL validation unless the narrow validator proves insufficient
- [ ] Long-term memory or personalization
- [ ] Auth, quotas, and rate limiting
- [ ] Multi-agent orchestration
- [ ] Microservice extraction
- [ ] Frontend/dashboard work
