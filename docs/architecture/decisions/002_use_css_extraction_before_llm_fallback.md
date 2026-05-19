# ADR 002: Use CSS Extraction Before LLM Fallback

## Status

Accepted.

## Context

Detail pages can often be extracted cheaply from page structure, but page markup is not always reliable.

## Decision

Try CSS extraction first, then fall back to raw markdown when CSS extraction is weak or incomplete.

## Consequences

- lower cost when page structure is stable
- faster extraction when selectors work
- fallback behavior still preserves data when CSS extraction degrades
- selector drift must be monitored
