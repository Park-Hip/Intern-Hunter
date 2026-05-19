# Dirty Worktree Cleanup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely preserve the current dirty worktree, split it into reviewable change buckets, and clean the original workspace only after each useful slice has been extracted into its own branch or worktree.

**Architecture:** Treat the current dirty worktree as a source pile, not as the place to clean in place. Extract changes into fresh worktrees from a clean base branch so docs reorganization, ETL/runtime changes, and local artifacts can be handled independently and safely.

**Tech Stack:** Git, PowerShell, worktrees, pytest

---

## File Structure

**Keep as source only**
- `D:\Data_Science_Project\job_finder`
  - Current dirty workspace.
  - Do not reset or broadly clean until extraction is complete.

**Create**
- `C:\tmp\job_finder-docs-reorg`
  - Clean worktree for the docs reorganization slice.
- `C:\tmp\job_finder-etl-runtime`
  - Clean worktree for ETL/runtime/schema-facing changes.
- Optional later:
  - `C:\tmp\job_finder-artifact-cleanup`
  - Only if `.gitignore` or artifact policy work becomes its own branch.

**Target branches**
- `backup/dirty-worktree-2026-05-19`
  - Safety name for the dirty state.
- `codex/docs-reorg-cleanup`
  - Extracted docs move/reorg work.
- `codex/etl-runtime-review`
  - Extracted runtime change review branch.
- Optional later:
  - `codex/local-artifact-cleanup`

## Change Buckets From The Audit

### Bucket 1: Docs Reorganization

These look like an intentional docs information-architecture move and should be reviewed separately from code:

- deleted:
  - `docs/AGENT_API_CONTRACT.md`
  - `docs/AGENT_ARCHITECTURE.md`
  - `docs/AGENT_DATA_DICTIONARY.md`
  - `docs/AGENT_EVAL_SET.md`
  - `docs/AGENT_SECURITY_MODEL.md`
  - `docs/AGENT_SQL_CONTRACT.md`
  - `docs/AGENT_VISION.md`
  - `docs/CURRENT_BEHAVIOR.md`
  - `docs/ETL_CRAWLER_SEMANTICS.md`
  - `docs/PROCESSOR_CONTRACT.md`
  - `docs/SETUP.md`
  - `docs/api/endpoints.md`
  - `docs/api/errors.md`
  - `docs/api/models.md`
  - `md/JobFinder_Second_Brain.md`
  - `md/architecture.md`
  - `md/architecture_map.md`
  - `md/etl_map.md`
  - `md/mvp_plan.md`
- added or reorganized:
  - `docs/agent/*`
  - `docs/current-system/*`
  - `docs/getting-started/setup.md`
  - `docs/api/overview.md`
  - `docs/superpowers/*`
- modified:
  - `README.md`
  - `docs/README.md`
  - `docs/architecture/*`
  - `docs/development/ai_workflow.md`
  - `docs/examples/search_examples.md`
  - `docs/operations/*`

### Bucket 2: ETL / Runtime / Schema-Facing Code

These are sensitive because several touch frozen or semi-frozen areas:

- `src/config/prompts.yaml`
- `src/core/models/job.py`
- `src/internhunter/api/routes/demo_routes.py`
- `src/internhunter/config/settings.py`
- `src/internhunter/extraction/job_processor.py`
- `src/internhunter/extraction/validator.py`
- `src/internhunter/llm/providers.py`
- `src/internhunter/resume/matching.py`
- `src/internhunter/search/repository.py`
- `src/internhunter/storage/models.py`
- `src/internhunter/storage/repositories/etl.py`
- `src/scripts/upgrade_db.py`
- `tests/conftest.py`
- `tests/unit/test_demo_api_routes.py`
- `tests/unit/test_etl_repository.py`
- `tests/unit/test_job_processor.py`
- `tests/unit/test_resume_matching_tools.py`
- `tests/unit/test_search_repository.py`
- `tests/unit/test_prompt_configuration.py`

### Bucket 3: Local / Generated / Policy Decisions

- `mlflow.db`
- `.codex_skill_build/`
- `AGENTS.md`

These should be reviewed for ignore policy or kept out of feature commits unless intentionally needed.

## Task 1: Preserve The Dirty State Before Any Cleanup

**Files:**
- No file edits.
- Protect current workspace state first.

- [ ] **Step 1: Confirm current branch and dirty status**

Run:

```powershell
git branch --show-current
git status --short
```

Expected:
- branch is still the long-running local branch
- dirty changes are present

- [ ] **Step 2: Create a safety branch name for the dirty state**

Run:

```powershell
git switch -c backup/dirty-worktree-2026-05-19
```

Expected:
- new local branch created
- dirty changes remain in the working tree unchanged

- [ ] **Step 3: Record the dirty snapshot for human review**

Run:

```powershell
git status --short > C:\tmp\job_finder_dirty_snapshot_2026-05-19.txt
git diff --stat >> C:\tmp\job_finder_dirty_snapshot_2026-05-19.txt
```

Expected:
- one text snapshot exists in `C:\tmp`

- [ ] **Step 4: Do not commit or reset anything in the source worktree**

Rule:
- no `git reset --hard`
- no `git clean -fd`
- no `git checkout -- .`

## Task 2: Extract The Docs Reorganization Into A Clean Worktree

**Files:**
- Create worktree: `C:\tmp\job_finder-docs-reorg`
- Source: dirty workspace docs files
- Target branch: `codex/docs-reorg-cleanup`

- [ ] **Step 1: Create a clean worktree from `origin/main`**

Run:

```powershell
git worktree add C:\tmp\job_finder-docs-reorg -b codex/docs-reorg-cleanup origin/main
```

Expected:
- clean worktree created at `C:\tmp\job_finder-docs-reorg`

- [ ] **Step 2: Copy only docs-related changes from the dirty source**

Use file-by-file copying from:
- `D:\Data_Science_Project\job_finder`
to:
- `C:\tmp\job_finder-docs-reorg`

Copy these directories/files exactly:

```text
README.md
docs/README.md
docs/agent/
docs/current-system/
docs/getting-started/
docs/api/overview.md
docs/architecture/
docs/development/ai_workflow.md
docs/examples/search_examples.md
docs/operations/
docs/superpowers/
```

Also remove in the clean worktree the old docs that were intentionally replaced:

```text
docs/AGENT_API_CONTRACT.md
docs/AGENT_ARCHITECTURE.md
docs/AGENT_DATA_DICTIONARY.md
docs/AGENT_EVAL_SET.md
docs/AGENT_SECURITY_MODEL.md
docs/AGENT_SQL_CONTRACT.md
docs/AGENT_VISION.md
docs/CURRENT_BEHAVIOR.md
docs/ETL_CRAWLER_SEMANTICS.md
docs/PROCESSOR_CONTRACT.md
docs/SETUP.md
docs/api/endpoints.md
docs/api/errors.md
docs/api/models.md
md/JobFinder_Second_Brain.md
md/architecture.md
md/architecture_map.md
md/etl_map.md
md/mvp_plan.md
docs/development/migrations.md
```

- [ ] **Step 3: Verify the docs reorg is self-consistent**

Run:

```powershell
git status --short
rg "AGENT_API_CONTRACT|AGENT_ARCHITECTURE|AGENT_DATA_DICTIONARY|AGENT_EVAL_SET|AGENT_SECURITY_MODEL|AGENT_SQL_CONTRACT|AGENT_VISION|CURRENT_BEHAVIOR|ETL_CRAWLER_SEMANTICS|PROCESSOR_CONTRACT|SETUP" docs README.md
```

Expected:
- `git status` shows mostly docs changes
- `rg` finds either zero stale references or only references intentionally describing the move

- [ ] **Step 4: Stage and review only docs changes**

Run:

```powershell
git add README.md docs md
git diff --cached --stat
```

Expected:
- staged diff contains docs only

- [ ] **Step 5: Commit the docs reorganization branch**

Run:

```powershell
git commit -m "docs: reorganize agent and system documentation"
```

## Task 3: Extract The ETL / Runtime Slice Into A Separate Review Branch

**Files:**
- Create worktree: `C:\tmp\job_finder-etl-runtime`
- Source: dirty workspace runtime/code files
- Target branch: `codex/etl-runtime-review`

- [ ] **Step 1: Create a second clean worktree from `origin/main`**

Run:

```powershell
git worktree add C:\tmp\job_finder-etl-runtime -b codex/etl-runtime-review origin/main
```

Expected:
- clean worktree created at `C:\tmp\job_finder-etl-runtime`

- [ ] **Step 2: Copy only runtime/code/test files from the dirty source**

Copy these files from the dirty source worktree:

```text
src/config/prompts.yaml
src/core/models/job.py
src/internhunter/api/routes/demo_routes.py
src/internhunter/config/settings.py
src/internhunter/extraction/job_processor.py
src/internhunter/extraction/validator.py
src/internhunter/llm/providers.py
src/internhunter/resume/matching.py
src/internhunter/search/repository.py
src/internhunter/storage/models.py
src/internhunter/storage/repositories/etl.py
src/scripts/upgrade_db.py
tests/conftest.py
tests/unit/test_demo_api_routes.py
tests/unit/test_etl_repository.py
tests/unit/test_job_processor.py
tests/unit/test_resume_matching_tools.py
tests/unit/test_search_repository.py
tests/unit/test_prompt_configuration.py
```

- [ ] **Step 3: Review for frozen-area violations before any commit**

Run:

```powershell
git diff --stat
rg "clean_jobs|raw_jobs|company|upgrade_db|job_processor|validator|provider" -n src tests
```

Review questions:
- does this slice change frozen ETL behavior?
- does this slice change `raw_jobs` / `clean_jobs` schema?
- does this slice change provider behavior unexpectedly?

If yes:
- stop and split again before committing

- [ ] **Step 4: Run only the smallest relevant tests for this slice**

Run:

```powershell
uv run pytest tests\unit\test_demo_api_routes.py tests\unit\test_etl_repository.py tests\unit\test_job_processor.py tests\unit\test_resume_matching_tools.py tests\unit\test_search_repository.py tests\unit\test_prompt_configuration.py -v
```

Expected:
- either tests pass
- or failures clearly identify whether this slice is still worth keeping

- [ ] **Step 5: Only commit if the slice is still intentional after review**

Run:

```powershell
git add src tests
git commit -m "feat: preserve pending etl and runtime changes for review"
```

If this review shows the slice is unwanted or crosses frozen boundaries:
- do not commit
- instead document the findings and discard the clean worktree

## Task 4: Handle Local / Generated Artifacts Safely

**Files:**
- `mlflow.db`
- `.codex_skill_build/`
- optional `.gitignore` changes later

- [ ] **Step 1: Decide whether `mlflow.db` is intentional project state or local noise**

Run:

```powershell
git ls-files mlflow.db
```

Expected:
- if tracked: treat as policy decision before deleting
- if untracked in future branches: prefer ignoring it

- [ ] **Step 2: Keep `.codex_skill_build/` out of commits**

Rule:
- do not stage `.codex_skill_build/`

Optional later:

```powershell
Add-Content .gitignore ".codex_skill_build/"
```

Only do this in a dedicated cleanup branch if the team wants the ignore rule committed.

- [ ] **Step 3: Do not delete tracked local artifacts from the source worktree until their policy is explicit**

Rule:
- if `mlflow.db` is tracked, do not remove it casually from the dirty source tree

## Task 5: Clean The Original Dirty Worktree Only After Extraction Is Safe

**Files:**
- source worktree only

- [ ] **Step 1: Confirm useful work now exists elsewhere**

Checklist:
- docs reorg branch exists with commit
- runtime review branch either exists with commit or was intentionally discarded
- pushed agent branch already exists separately

- [ ] **Step 2: Choose one cleanup mode for the original dirty tree**

Option A: keep as local sandbox

Run:

```powershell
git branch --show-current
git status --short
```

Then leave it alone.

Option B: return it to a clean branch after extraction is safe

Run only after confirming all desired work exists elsewhere:

```powershell
git switch main
git fetch origin
git reset --hard origin/main
git clean -fd
```

Warning:
- Option B is destructive and must only happen after the extracted branches are verified

## Spec Coverage Check

- preserve dirty state first:
  - Task 1
- split by docs reorg, ETL/runtime, local artifacts:
  - Tasks 2, 3, 4
- avoid risky in-place cleanup:
  - Tasks 1 and 5
- produce a safe path to a clean workspace:
  - Task 5

No coverage gaps found for the cleanup goal.

## Known Risks

- `src/internhunter/storage/models.py`, `src/internhunter/storage/repositories/etl.py`, `src/scripts/upgrade_db.py`, and `src/internhunter/extraction/job_processor.py` may cross frozen boundaries and should not be committed without explicit review.
- The docs reorganization may contain hidden broken links or stale references after file moves.
- `mlflow.db` may be tracked history rather than disposable local state, so policy matters before deletion.
- Cleaning the original dirty worktree before extraction is complete risks permanent loss.

## Verification Commands

Dirty snapshot:

```powershell
git status --short
git diff --stat
```

Docs reorg verification:

```powershell
git -C C:\tmp\job_finder-docs-reorg status --short
git -C C:\tmp\job_finder-docs-reorg diff --stat
```

Runtime slice verification:

```powershell
git -C C:\tmp\job_finder-etl-runtime status --short
uv run pytest tests\unit\test_demo_api_routes.py tests\unit\test_etl_repository.py tests\unit\test_job_processor.py tests\unit\test_resume_matching_tools.py tests\unit\test_search_repository.py tests\unit\test_prompt_configuration.py -v
```
