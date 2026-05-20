from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentRuntimeInput(BaseModel):
    """Validated input payload for the agent runtime layer."""

    model_config = ConfigDict(extra="forbid")

    question: str
    session_id: str | None = None
    user_id: str | None = None
    preview_only: bool = False

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        """Reject empty questions before runtime invocation."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("question cannot be empty.")
        return normalized

    @field_validator("session_id", "user_id")
    @classmethod
    def normalize_optional_ids(cls, value: str | None) -> str | None:
        """Normalize optional identifiers into trimmed strings or None."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AgentRuntimeOutput(BaseModel):
    """Typed response emitted by the runtime foundation."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    warnings: list[str] = Field(default_factory=list)
    trace_id: str

