# ADR 001: Use a Modular Monolith

## Status

Accepted.

## Context

The project has crawler, processor, database, and orchestration code that need to evolve together.

## Decision

Keep the system in one deployable codebase and organize it into clear module boundaries.

## Consequences

- simpler local development
- easier shared model reuse
- more discipline needed around module boundaries
- future services can still be split out later if the code stabilizes
