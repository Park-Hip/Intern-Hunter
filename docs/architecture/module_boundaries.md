# Module Boundaries

## Config

Responsibilities:
- load environment settings and YAML config
- centralize prompt lookup
- expose crawler and model defaults

Must not:
- talk to the database
- call LLM APIs directly
- contain business rules

## Common

Responsibilities:
- shared pure helpers and shared data models
- typed request and result objects

Must not:
- depend on infrastructure
- perform I/O

## Ingestion

Responsibilities:
- discover listing pages
- crawl job detail pages
- normalize URLs
- stage raw jobs

Must not:
- validate business policy
- save structured job results
- expose API endpoints

## Extraction

Responsibilities:
- convert raw page content into structured job data
- choose between CSS extraction and raw fallback

Must not:
- own database transactions
- own orchestration
- perform unrelated search logic

## Storage

Responsibilities:
- own ORM models
- own sessions and repository methods
- enforce persistence rules

Must not:
- call crawlers
- call LLM providers directly unless through a service boundary
- contain orchestration logic

## Embeddings

Responsibilities:
- build text for vectorization
- generate embeddings
- handle translation before embedding when needed

Must not:
- change raw crawl data
- decide whether a job is valid

## Resume

Responsibilities:
- store resume text and resume vectors
- compare resume vectors against job vectors
- support matching workflows

Must not:
- scrape TopCV
- parse crawl pages

## Search

Responsibilities:
- filter jobs by structured criteria
- perform similarity search with pgvector

Must not:
- mutate jobs
- perform ingestion or extraction

## Orchestration

Responsibilities:
- sequence tasks
- apply retries and telemetry
- define pipeline entry points

Must not:
- embed business rules that belong in services

## API

Responsibilities:
- expose the public search and resume demo endpoints
- translate HTTP requests into service calls

Must not:
- hold persistence logic
- implement crawling or LLM rules
