# InternHunter Migration Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the dependent `src/internhunter/*` code path and the new docs layout into one self-consistent branch, so the extracted docs and runtime changes can be reviewed together instead of remaining broken snapshots against `origin/main`.

**Architecture:** Treat this as a reconciliation branch, not a feature branch. Start from the preserved snapshots, establish the real intended runtime entrypoints and package layout, then either (a) complete the `src/internhunter/*` migration enough that the docs and tests become truthful, or (b) intentionally roll specific docs/code paths back to the current `origin/main` structure. The branch must become internally consistent before any further agent work builds on it.

**Tech Stack:** Git worktrees, Python package layout review, FastAPI, pytest, docs verification

---

## Why This Plan Exists

Two extracted snapshots proved the same thing:

- `codex/docs-reorg-cleanup` is docs-only, but its content assumes a newer runtime/layout than `origin/main`
- `codex/etl-runtime-review` is code/test-only, but it is not self-contained on `origin/main`

So the repo is currently in the middle of a dependent migration involving:

- a new docs information architecture
- a `src/internhunter/*` package layout
- agent/runtime/search/resume code that partially expects that layout
- tests that partially expect that layout

This plan is for reconciling that migration deliberately instead of treating the dirty tree as independent cleanup slices.

## Current Preserved States

Use these as inputs:

- Source backup:
  - current branch `backup/dirty-worktree-2026-05-19`
- Docs snapshot:
  - worktree `C:\tmp\job_finder-docs-reorg`
  - branch `codex/docs-reorg-cleanup`
  - commit `5ab0c6e`
- Runtime snapshot:
  - worktree `C:\tmp\job_finder-etl-runtime`
  - branch `codex/etl-runtime-review`
  - unstaged/uncommitted review copy

## Reconciliation Objective

Produce one branch where all of the following are simultaneously true:

- docs point to real files and real entrypoints
- package paths used in code, tests, and docs agree
- the app entrypoint for current API behavior is unambiguous
- the new agent work can be built on top without depending on broken snapshots
- frozen-area changes are either explicitly justified or excluded

## File Structure Strategy

**Create**
- `C:\tmp\job_finder-reconcile`
  - clean reconciliation worktree from `origin/main`
- optional audit notes file:
  - `docs/superpowers/plans/2026-05-19-internhunter-reconciliation-notes.md`

**Potentially modify during reconciliation**
- `README.md`
- `docs/**`
- `src/main.py`
- `src/internhunter/**`
- `src/infrastructure/**`
- `src/services/**`
- `tests/**`

**Do not modify casually**
- frozen ETL/crawler behavior files unless the reconciliation cannot be made internally consistent without them

## Guiding Decision Rules

- Prefer **making docs truthful to code** over inventing missing runtime paths.
- Prefer **restoring consistency** over preserving every single draft change.
- If two paths exist (`src/internhunter/*` and older `src/infrastructure/*`/`src/services/*`), choose one as canonical per subsystem and make references consistent.
- Do not force the entire repo to migrate at once if a narrower compatibility layer can make the branch self-consistent.
- Treat `src/internhunter/api/app.py` and `src/main.py` as a first-class decision point early in the plan.

## Task 1: Create A Reconciliation Worktree And Baseline Inventory

**Files:**
- Create: `C:\tmp\job_finder-reconcile`
- Read:
  - `C:\tmp\job_finder-docs-reorg`
  - `C:\tmp\job_finder-etl-runtime`
  - `D:\Data_Science_Project\job_finder`

- [ ] **Step 1: Create a clean worktree from `origin/main`**

Run:

```powershell
git worktree add C:\tmp\job_finder-reconcile -b codex/internhunter-reconcile origin/main
```

Expected:
- clean worktree exists at `C:\tmp\job_finder-reconcile`

- [ ] **Step 2: Record the real `origin/main` runtime layout**

Run:

```powershell
rg "FastAPI|include_router|APIRouter|uvicorn" -n src
rg --files src
```

Expected:
- concrete inventory of actual app/runtime entrypoints on `origin/main`

- [ ] **Step 3: Record the migration expectations from the snapshots**

Run:

```powershell
rg "src\\.internhunter|uvicorn src\\.internhunter\\.api\\.app:app|api_demo_smoke|semantic_search_smoke" -n README.md docs src tests
```

Run this in:
- `C:\tmp\job_finder-docs-reorg`
- `C:\tmp\job_finder-etl-runtime`

Expected:
- clear list of which files assume the new layout

- [ ] **Step 4: Write a short reconciliation inventory note**

Capture:
- actual `origin/main` entrypoints
- expected `src/internhunter/*` entrypoints from snapshots
- missing modules/scripts/docs links

This note can live at:

```text
docs/superpowers/plans/2026-05-19-internhunter-reconciliation-notes.md
```

## Task 2: Decide The Canonical Runtime Entry Surface

**Files:**
- Read:
  - `src/main.py`
  - any `src/internhunter/api/app.py` snapshot copy
  - docs that mention `uvicorn`

- [ ] **Step 1: Compare the two runtime entry models**

Model A:
- current `origin/main` runtime via `src/main.py`

Model B:
- new direct API entry via `src/internhunter/api/app.py`

Assess:
- which one actually exists on `origin/main`
- which one the docs now describe
- which one the new tests import

- [ ] **Step 2: Choose one of two reconciliation directions**

Direction 1: compatibility-first
- keep `src/main.py` as canonical
- make docs and tests stop claiming `src.internhunter.api.app` exists unless it will really be added

Direction 2: migration-forward
- add and wire `src/internhunter/api/app.py` as a real supported entrypoint
- keep `src/main.py` only if it remains intentionally supported

- [ ] **Step 3: Do not proceed until this decision is explicit**

If the decision is not obvious from repo intent:
- stop and ask the user before changing code

## Task 3: Reconcile The `src/internhunter/*` Namespace Surface

**Files:**
- `src/internhunter/**`
- `src/infrastructure/**`
- `src/services/**`
- tests that import either path family

- [ ] **Step 1: Build a mapping table**

For each imported `src.internhunter.*` path in the snapshots, determine:
- already exists on `origin/main`
- has an older equivalent elsewhere
- missing entirely

Minimum targets to classify:

```text
src.internhunter.api.app
src.internhunter.common.logging
src.internhunter.storage.session
src.internhunter.embeddings
src.internhunter.resume.repository
src.internhunter.llm.router
src.internhunter.llm.base
src.internhunter.search.repository
src.internhunter.storage.models
src.internhunter.storage.repositories.etl
```

- [ ] **Step 2: Pick a reconciliation mechanism per path**

Possible mechanisms:
- restore older imports in docs/tests/code
- add thin compatibility modules that forward to existing implementations
- complete the newer module move for a narrow subset

Rule:
- prefer thin compatibility shims where they reduce migration cost without hiding behavior

- [ ] **Step 3: Keep the scope narrow**

Do not migrate the full codebase just because both layouts exist.
Only reconcile the modules required to make:
- docs truthful
- tests importable
- agent/runtime baseline coherent

## Task 4: Reconcile Docs To The Chosen Runtime Truth

**Files:**
- `README.md`
- `docs/README.md`
- `docs/current-system/**`
- `docs/getting-started/**`
- `docs/api/**`
- `docs/architecture/**`

- [ ] **Step 1: Fix missing file references**

Examples already known from review:
- `docs/development/testing.md`
- `docs/development/code_style.md`
- `docs/development/logging.md`
- `docs/examples/local_ingestion.md`
- `docs/examples/run_scraper.md`
- `docs/examples/run_embeddings.md`

For each:
- create the missing doc if it is genuinely intended and useful
- or remove/update the link if it is not real

- [ ] **Step 2: Fix stale runtime commands**

Examples already known from review:
- `uvicorn src.internhunter.api.app:app`
- missing smoke scripts:
  - `src/scripts/semantic_search_smoke.py`
  - `src/scripts/api_demo_smoke.py`

Replace these with:
- real current commands
- or real new commands only after the code exists

- [ ] **Step 3: Fix contradictory statements**

Known contradiction:
- docs say `src/main.py` was intentionally removed
- but `src/main.py` exists on `origin/main`

Resolve all such contradictions before the branch is considered trustworthy.

## Task 5: Reconcile Tests To The Chosen Layout

**Files:**
- `tests/**`

- [ ] **Step 1: Classify tests into three groups**

Group A:
- tests that already match `origin/main`

Group B:
- tests that assume the new `src/internhunter/*` layout but could use compatibility shims

Group C:
- tests that belong to future agent/runtime work and should not be forced into this migration branch yet

- [ ] **Step 2: Keep only the tests that the reconciled branch can honestly support**

Do not keep tests that require unimplemented future layout unless the code is being added in the same branch.

- [ ] **Step 3: Normalize encoding drift**

Fix BOM/encoding issues in any touched Python files before final review.

## Task 6: Review Frozen-Area Touches Explicitly

**Files:**
- `src/internhunter/extraction/job_processor.py`
- `src/internhunter/storage/models.py`
- `src/internhunter/storage/repositories/etl.py`
- `src/scripts/upgrade_db.py`
- any ETL/crawler-related tests

- [ ] **Step 1: Compare each touched frozen-area file against `AGENTS.md`**

For each file, decide:
- required for reconciliation consistency
- optional drift that should be excluded from this branch

- [ ] **Step 2: Exclude anything that is not required**

If a touched file is not necessary to make the branch self-consistent:
- remove it from the reconciliation branch
- leave it in the backup dirty branch only

- [ ] **Step 3: Escalate if a true frozen-area change is required**

Before committing a frozen-area change, prepare a concise explanation:
- why it is necessary
- what dependency forced it
- why it cannot be deferred

## Task 7: Build A Self-Consistent Reconciliation Branch

**Files:**
- all selected reconciled code/docs/tests

- [ ] **Step 1: Stage only the reconciled set**

Run:

```powershell
git add <selected files only>
git diff --cached --stat
```

Expected:
- staged set is coherent and intentionally scoped

- [ ] **Step 2: Run the smallest truthful test/doc verification set**

Possible commands:

```powershell
uv run pytest <selected tests> -v
rg "uvicorn src\\.internhunter\\.api\\.app:app|api_demo_smoke|semantic_search_smoke" README.md docs
rg "src\\.internhunter|src\\.infrastructure|src\\.services" -n README.md docs tests src
```

Expected:
- no obviously broken doc commands
- no import-path contradictions in the selected slice

- [ ] **Step 3: Commit only if the branch is internally consistent**

Suggested commit message:

```text
chore: reconcile internhunter migration layout and docs
```

If still inconsistent:
- do not commit
- stop and report the remaining contradictions

## Task 8: Decide What To Do With The Two Snapshot Branches

**Files:**
- `codex/docs-reorg-cleanup`
- `codex/etl-runtime-review`

- [ ] **Step 1: Keep them as provenance snapshots until reconciliation succeeds**

Do not delete immediately.

- [ ] **Step 2: After successful reconciliation, decide whether to**

- keep the snapshot branches as history
- or discard them once the reconciled branch supersedes them

## Spec Coverage Check

- explains why independent cleanup failed:
  - intro and Task 1
- creates a deliberate migration/reconciliation branch:
  - Tasks 1 through 7
- addresses dependent `src/internhunter/*` plus docs drift together:
  - Tasks 2 through 5
- explicitly reviews frozen-area risk:
  - Task 6
- keeps preserved snapshots as provenance:
  - Task 8

No coverage gaps found for the reconciliation goal.

## Known Risks

- The branch may reveal that the `src/internhunter/*` migration is only partially specified and needs an explicit architectural decision.
- Compatibility shims can reduce migration pain, but too many shims can hide real drift and create long-term confusion.
- Frozen-area files may be entangled with the migration, which means the branch could require explicit user approval before final integration.
- Docs may need a second pass even after path reconciliation, because some content may describe behavior that no longer exists conceptually, not just by file path.

## Verification Commands

Baseline inventory:

```powershell
rg "FastAPI|include_router|APIRouter|uvicorn" -n src
rg --files src
```

Path-drift inventory:

```powershell
rg "src\\.internhunter|src\\.infrastructure|src\\.services|uvicorn src\\.internhunter\\.api\\.app:app|api_demo_smoke|semantic_search_smoke" -n README.md docs src tests
```

Reconciled branch verification:

```powershell
uv run pytest <selected tests> -v
git diff --cached --stat
git status --short
```
