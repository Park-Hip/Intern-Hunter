# ADR 003: Use Multiple LLM Providers for Extraction Fallback

## Status

Accepted.

## Context

LLM extraction depends on external providers that can fail or rate limit unpredictably.

## Decision

Use Gemini as the primary provider and Groq as the fallback provider for job parsing and translation.

## Consequences

- better availability than a single provider
- more complex prompt and response handling
- provider differences may affect output consistency
