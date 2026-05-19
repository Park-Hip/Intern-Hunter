# Data Contracts

Current contracts based on the live ORM models, repository outputs, and API route inputs.

## RawJobPage

- `url: string`
- `crawl_run_id: string | null`
- `source_seed_url: string | null`
- `title: string | null`
- `company: string | null`
- `location: string | null`
- `full_json_dump: object | null`
- `status: string`
- `extraction_method: string`
- `raw_markdown: string | null`
- `html_content: string | null`
- `screenshot_path: string | null`
- `retry_count: number`
- `created_at: string`
- `updated_at: string | null`
- `last_crawled_at: string | null`

## ExtractedJob / ProcessedJob

- `standardized_title: string`
- `job_level: string | null`
- `is_internship: boolean`
- `description: string | null`
- `requirement: string | null`
- `benefit: string | null`
- `cities: string[]`
- `experience: number | null`
- `min_gpa: number | null`
- `english_requirement: string | null`
- `salary_min: number | null`
- `salary_max: number | null`
- `currency: string | null`
- `is_salary_negotiable: boolean`
- `tech_stack: string[]`
- `technical_competencies: string[]`
- `domain_knowledge: string[]`
- `embedding: number[768] | null`
- `created_at: string`

## UserProfile / ResumeProfile

- `id: number`
- `user_id: string`
- `resume_text: string`
- `resume_embedding: number[768] | null`
- `created_at: string`
- `updated_at: string | null`

## Search Request Shape

Repository criteria search accepts:

- `title: string[] | null`
- `job_level: string[] | null`
- `cities: string[] | null`
- `experience: number | null`
- `limit: number`

API search also accepts:

- `query: string`
- `mode: "criteria" | "semantic"`

## Search Result Shape

- `title: string`
- `level: string`
- `company: string`
- `cities: string[]`
- `experience_required_years: number | null`
- `salary_range: string`
- `url: string`
- `match_score: number | null`

Criteria search may omit `match_score`.

## Resume Match Request

- `user_id: string`
- `resume_text: string`
- `limit: number`

## Resume Match Result

- `title: string`
- `level: string`
- `company: string`
- `cities: string[]`
- `experience_required_years: number | null`
- `salary_range: string`
- `url: string`
- `match_score: number | null`
- `matched_skills: string[]`
- `unmatched_resume_skills: string[]`
- `reason: string`
