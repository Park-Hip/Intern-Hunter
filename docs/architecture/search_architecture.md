# Search Architecture

Current search behavior is split across two paths:

- structured filtering through `SearchRepository.search_jobs_by_criteria()`
- vector similarity search through `SearchRepository.search_jobs_by_similarity()`

## Structured Search

- filters by title
- filters by job level
- filters by cities
- filters by experience
- returns mapped job summaries

## Similarity Search

- uses the `clean_jobs.embedding` column
- queries with pgvector cosine distance
- returns mapped job summaries for ranking by similarity

## Current Gaps

- The public search endpoint is currently exposed through the demo API surface.
- SQL search remains a repository/helper capability rather than a first-class public endpoint.
- Resume matching lives in the canonical resume module and is exposed through the demo API.
