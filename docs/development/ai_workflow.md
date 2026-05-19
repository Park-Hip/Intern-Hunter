# AI-Assisted Refactoring Workflow

## Working Rules

- Read the docs before changing code.
- Keep diffs small and focused on one module at a time.
- Do not make unrelated edits in the same change.
- Add or update tests for any behavior change.
- Do not change the database schema without a migration or upgrade path.
- Do not add dependencies without a clear reason.

## Practical Workflow

1. Inspect the current module boundaries.
2. Identify the smallest safe change.
3. Make the change.
4. Verify with the narrowest useful test set.
5. Record any TODOs that remain.

## Guardrails

- Prefer move-only refactors first.
- Avoid changing more than one subsystem in a single AI-assisted pass.
- If a change touches a contract, update the matching docs and tests together.
- Preserve behavior until the code is covered by tests.
- Use existing patterns for logging, config, and repositories.
- Update docs when behavior changes.

## Change Shape

- One logical change per commit or checkpoint.
- Separate documentation-only changes from runtime code changes when possible.
- Capture a checkpoint before any behavior-changing step.

## Testing Expectation

- Unit tests should cover pure logic and mapping.
- Integration tests should cover the ETL flow and database writes.
