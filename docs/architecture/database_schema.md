# Database Schema

This is a draft schema summary based on `src/internhunter/storage/models.py`.

## `raw_jobs`

- `id`
- `url`
- `crawl_run_id`
- `source_seed_url`
- `title`
- `company`
- `location`
- `full_json_dump`
- `status`
- `extraction_method`
- `raw_markdown`
- `html_content`
- `screenshot_path`
- `retry_count`
- `created_at`
- `updated_at`
- `last_crawled_at`

## `clean_jobs`

- `id`
- `raw_job_id`
- `standardized_title`
- `company`
- `job_level`
- `is_internship`
- `description`
- `requirement`
- `benefit`
- `cities`
- `experience`
- `min_gpa`
- `english_requirement`
- `salary_min`
- `salary_max`
- `currency`
- `is_salary_negotiable`
- `tech_stack`
- `technical_competencies`
- `domain_knowledge`
- `embedding`
- `created_at`

## `audit_jobs`

- `id`
- `url`
- `crawl_run_id`
- `source_seed_url`
- `error_type`
- `error_message`
- `screenshot_path`
- `html_content`
- `created_at`

## `user_profiles`

- `id`
- `user_id`
- `resume_text`
- `resume_embedding`
- `created_at`
- `updated_at`

## `pipeline_runs`

- `id`
- `run_id`
- `timestamp`
- `jobs_acquired`
- `jobs_processed`
- `jobs_failed`
- `status`

## Notes

- This summary is derived from the live SQLAlchemy models in `src/internhunter/storage/models.py`.
- Relationship details, indexes, and database-level constraints should be verified from the live database when needed.
