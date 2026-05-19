# Resume Matching

Resume matching lives in the canonical resume module and is backed by `user_profiles`.

## Current Flow

1. A user uploads resume text through the resume API.
2. The resume text is embedded.
3. The embedding is stored with the user profile.
4. Matching uses pgvector similarity against `clean_jobs.embedding`.

## Current Storage

- resume text is stored in `user_profiles.resume_text`
- resume vector is stored in `user_profiles.resume_embedding`

## Notes

- If PDF or DOCX resume parsing is added later, document it under the resume module.
- If matching score normalization changes later, update this doc alongside the repository code.
