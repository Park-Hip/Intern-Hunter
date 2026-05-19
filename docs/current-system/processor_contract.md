# Job Processor Contract

This note defines the current boundary between deterministic parsing and LLM inference in the job processor. It is the stable reference for future prompts and processor changes.

## 1. Goal

Keep explicit page facts deterministic and reserve the LLM for semantic interpretation.

## 2. Direct Raw Mapping

These fields should be preserved directly from `raw_jobs.full_json_dump` or the raw row itself when present:

- `description`
- `requirements`
- `benefits`
- `title`
- `company`
- `location`

For TopCV, the direct clean-job text fields are:

- `description` -> `ProcessedJob.description` -> `CleanJobDB.description`
- `requirements` -> `ProcessedJob.requirement` -> `CleanJobDB.requirement`
- `benefits` -> `ProcessedJob.benefit` -> `CleanJobDB.benefit`

## 3. Deterministic Parser Hints

These fields should be handled by rule-based parsing or normalization before LLM inference when the signal is explicit:

- `work_location` -> location / cities hint
- `salary`
- `experience`
- internship/fresher detection
- obvious city normalization
- explicit English requirement markers
- obvious degree / GPA markers
- obvious keyword candidates for tech stack

The current MVP only requires:
- `title`
- `company`
- `description`
- `requirements`

## 4. LLM Inference

These fields remain semantic and are best left to the LLM or LLM-assisted cleanup:

- `standardized_title`
- `job_level`
- `tech_stack`
- `technical_competencies`
- `domain_knowledge`
- `english_requirement` refinement
- `min_gpa` when inferable from context

## 5. Raw-Only Evidence

These fields stay as evidence-only metadata for now:

- `working_time`
- `application_method`
- `section_sources`
- `extraction_version`
- `html_content`
- `raw_markdown`
- `screenshot_path`
- `full_json_dump`

## 6. Deterministic Mode

The deterministic processor mode should:

- skip LLM validation
- skip LLM transformation
- skip embeddings
- still persist a clean-job-compatible `ProcessedJob`
- remain backward compatible with old info-only raw rows

For the MVP pipeline, LLM job-validity validation is opt-in. The default shipping path should preserve the clean-job flow without making validation a gate.

## 7. Compatibility Rule

Do not move explicit page facts back into the LLM. If a field is already present in structured raw evidence, prefer deterministic preservation first.

## 8. MVP Reminder

For MVP shipping, the required fields are:

- `title`
- `company`
- `description`
- `requirements`

All other TopCV sections are useful, but they are not release blockers.
