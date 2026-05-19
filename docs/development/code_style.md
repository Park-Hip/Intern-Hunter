# Code Style

- Use type hints for public functions.
- Prefer Pydantic models for structured data.
- Use structlog instead of `print`.
- Keep repository methods focused on persistence.
- Keep services focused on business logic.
- Keep flow files focused on orchestration.
- Prefer small helpers over large nested blocks.

## Notes

- The repo already mixes legacy and newer patterns in a few places.
- TODO: normalize style only after behavior is pinned down by tests.
