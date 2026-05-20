# Database Agent Milestones

## Status

This is the active planning source of truth for the database-agent project.

The older planning docs:

- `docs/agent/database_agent_wave1_implementation_plan.md`
- `docs/agent/database_agent_mvp_roadmap.md`

are retained as historical references only. They are not the current execution plan.

## Planning Rules

The database-agent project now follows a milestone-first process:

1. Pick the next milestone at a high level.
2. Run a research gate before coding.
3. Close milestone-level design questions.
4. Write a milestone-specific coding plan only after the research/design work is approved.
5. Implement the milestone.
6. Update live behavior docs only when behavior actually ships.

Rules:

- Do not treat live docs as planning docs.
- Do not treat planning docs as implementation truth.
- Do not write a coding plan for a milestone before its research gate is closed.
- Do not silently lock architecture, tech stack, runtime, memory, tracing, or tool design choices without milestone-level research.

## Current Direction

The current agreed direction is:

- build the database agent as a separate agent-native subsystem under `src/agents/`
- keep the public entrypoint as `POST /agent/ask`
- grow the agent incrementally through milestones rather than through one long fixed implementation sequence
- keep tool growth incremental: prove the runtime, then add tools one by one
- keep unresolved architecture and tech-stack choices open until the relevant research gate closes them

Milestone 1 runtime decisions are now closed and partially shipped. Later milestone choices remain open until their own research gates close.

What is intentionally not decided here:

- Milestones after Milestone 1
- concrete persistent memory backend beyond the first short-session seam
- concrete tracing backend behind the first replaceable tracing seam

Those are milestone research decisions, not assumptions to bake in early.

## Milestones

### Milestone 1: Agent Runtime Foundation

**Goal**

Establish the first real agent runtime behind `POST /agent/ask` as a separate subsystem from ETL/runtime LLM code.

**Why it exists**

The agent runtime is the product center. It should be proven before deeper SQL, chart, or resume-tool work.

**Dependencies**

- current `/agent/ask` scaffold
- existing API contract baseline
- existing `src/agents/` package

**Locked Milestone 1 runtime note**

- LangChain agent entrypoint
- Ollama with `qwen3.5:4b` as the initial provider/model
- no tools in Milestone 1
- short session memory only
- tracing through a replaceable seam
- SQL generation and execution out of scope

**Research gate required before coding**

Closed for this milestone target.

**Questions to close**

- What runtime pattern should back the agent loop?
- What state model should the runtime use?
- What minimum runtime boundaries belong in `src/agents/` vs `src/services/query/`?
- How should the runtime stay separate from ETL LLM code while still reusing shared infra safely?

**Expected outputs**

- milestone design note
- runtime boundary decision
- module layout for the runtime foundation
- milestone-specific coding plan

**Ready for coding plan when...**

- runtime boundaries are explicit
- the separation from ETL/runtime LLM code is explicit
- the first runnable runtime target is defined clearly enough for implementation

### Milestone 2: Guardrail And Refusal Foundation

**Goal**

Define and implement the first real pre-agent safety layer and refusal behavior behind the runtime.

**Why it exists**

Unsafe or out-of-scope requests must be blocked before real tool execution is introduced.

**Dependencies**

- Milestone 1 runtime foundation

**Research gate required before coding**

Yes.

**Questions to close**

- Which categories belong in the guardrail?
- What is blocked before tool execution versus refused later by a tool?
- What refusal taxonomy should be surfaced publicly?
- What behavior belongs in deterministic screening versus later tool logic?

**Expected outputs**

- guardrail scope decision
- refusal taxonomy decision
- milestone-specific coding plan

**Ready for coding plan when...**

- pre-agent refusal boundaries are explicit
- deterministic screening scope is approved

### Milestone 3: SQL Preview Tool

**Goal**

Add the first real domain tool: generate SQL candidates safely without execution.

**Why it exists**

SQL preview proves the core database-agent workflow before execution risk is introduced.

**Dependencies**

- Milestone 1 runtime foundation
- Milestone 2 guardrail/refusal foundation

**Research gate required before coding**

Yes.

**Questions to close**

- How should schema/context be assembled for the agent?
- What prompt/runtime pattern should generate SQL candidates?
- What preview response contract should be treated as stable for this milestone?

**Expected outputs**

- SQL preview design
- provider/runtime decision for this milestone
- milestone-specific coding plan

**Ready for coding plan when...**

- SQL preview flow is explicit end-to-end
- no execution behavior is mixed into the milestone scope

### Milestone 4: SQL Validation And Execution

**Goal**

Add validated read-only execution for SQL generated by the agent.

**Why it exists**

This is the milestone where the agent becomes a true read-only database assistant.

**Dependencies**

- Milestone 3 SQL preview tool

**Research gate required before coding**

Yes.

**Questions to close**

- What exact validator strategy will be used?
- What execution boundary will enforce validated-only SQL?
- How should normalized table results be shaped?

**Expected outputs**

- validator design
- execution boundary design
- milestone-specific coding plan

**Ready for coding plan when...**

- validator responsibilities are explicit
- executor responsibilities are explicit
- table/result normalization responsibilities are explicit

### Milestone 5: Summary And Chart Output

**Goal**

Add result-grounded summaries and chart specs after safe SQL execution exists.

**Why it exists**

This milestone turns query results into a better user-facing analytics experience.

**Dependencies**

- Milestone 4 SQL execution

**Research gate required before coding**

Yes.

**Questions to close**

- How grounded should summaries be?
- What chartability rules should exist?
- What chart contract should be considered in-scope for the milestone?

**Expected outputs**

- summary/chart behavior design
- milestone-specific coding plan

**Ready for coding plan when...**

- chart generation is clearly result-driven
- no second execution path is introduced through charting

### Milestone 6: Resume Tool Integration

**Goal**

Add bounded agent access to the existing resume matching capability.

**Why it exists**

Resume matching is part of the product surface, but it must remain bounded and separate from SQL scope.

**Dependencies**

- Milestone 1 runtime foundation
- Milestone 2 guardrail/refusal foundation

**Research gate required before coding**

Yes.

**Questions to close**

- What exact adapter shape should wrap the existing resume logic?
- How should `user_id` be required and validated?
- How should resume results fit the shared response envelope?

**Expected outputs**

- resume-tool boundary design
- milestone-specific coding plan

**Ready for coding plan when...**

- resume-tool inputs/outputs are explicit
- SQL scope separation is explicit

### Milestone 7: Memory And Follow-Up Behavior

**Goal**

Add persistent bounded session follow-up behavior.

**Why it exists**

The agent should support follow-up workflows, but only after runtime/tool boundaries are stable enough to support them safely.

**Dependencies**

- Milestones 1 through 4 at minimum

**Research gate required before coding**

Yes.

**Questions to close**

- What memory backend should be used first?
- What data should be stored?
- What follow-up behaviors are in-scope?
- How should tracing and memory interact?

**Expected outputs**

- memory/seam design
- persistence backend decision
- milestone-specific coding plan

**Ready for coding plan when...**

- memory retention and trust boundaries are explicit
- the first persistence choice is approved

### Milestone 8: Acceptance Hardening And Docs Sync

**Goal**

Turn the assembled agent system into a tested and documented MVP slice.

**Why it exists**

The repo should not claim behavior that is not tested or documented.

**Dependencies**

- all earlier shipped milestones

**Research gate required before coding**

Usually no broad architecture research gate, but milestone-level acceptance criteria should still be explicit before implementation or cleanup work starts.

**Questions to close**

- What acceptance cases are required now?
- Which docs move from planned to implemented behavior?
- What tracing/verification evidence is required?

**Expected outputs**

- acceptance checklist
- doc sync checklist
- milestone-specific coding plan if needed

**Ready for coding plan when...**

- acceptance targets are explicit
- affected live docs are identified

## Status Tracking

Track progress at the milestone level only.

Suggested statuses:

- `not started`
- `research gate active`
- `ready for coding plan`
- `implementation active`
- `implemented`

Current status suggestion:

- Milestone 1: `implementation active` (runtime foundation is live; SQL, charts, and resume tools are still pending later milestones)
- Milestones 2-8: `not started`
