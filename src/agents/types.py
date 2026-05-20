from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RefusalCode(StrEnum):
    UNSAFE_SQL = "unsafe_sql"
    UNSUPPORTED_REQUEST = "unsupported_request"
    MISSING_REQUIRED_CONTEXT = "missing_required_context"
    INTERNAL_ERROR = "internal_error"


class RefusalCategory(StrEnum):
    SENSITIVE_CONTENT = "sensitive_content"
    PROMPT_INJECTION = "prompt_injection"
    DESTRUCTIVE_REQUEST = "destructive_request"
    DISALLOWED_STATEMENT = "disallowed_statement"
    MULTI_STATEMENT = "multi_statement"
    UNKNOWN_TABLE = "unknown_table"
    UNKNOWN_COLUMN = "unknown_column"
    NON_WHITELISTED_COLUMN = "non_whitelisted_column"
    MISSING_LIMIT = "missing_limit"
    EXCESSIVE_LIMIT = "excessive_limit"
    FORBIDDEN_WILDCARD_SELECT = "forbidden_wildcard_select"
    FORBIDDEN_JOIN = "forbidden_join"
    FORBIDDEN_CTE = "forbidden_cte"
    FORBIDDEN_SUBQUERY = "forbidden_subquery"
    FORBIDDEN_TEXT_MATCH = "forbidden_text_match"
    FORBIDDEN_LONG_TEXT_REFERENCE = "forbidden_long_text_reference"
    UNSUPPORTED_QUERY_FORM = "unsupported_query_form"
    UNSUPPORTED_QUESTION = "unsupported_question"
    OUT_OF_SCOPE = "out_of_scope"
    MISSING_USER_ID = "missing_user_id"
    INTERNAL_ERROR = "internal_error"


class TableArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = Field(0, ge=0)

    @model_validator(mode="after")
    def validate_row_count(self) -> TableArtifact:
        if self.row_count != len(self.rows):
            raise ValueError("row_count must match the number of rows.")
        return self


class SummaryArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("summary text cannot be empty.")
        return normalized


class ChartArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chart_type: str | None = None
    chart_spec: dict[str, Any] | None = None
    warning: str | None = None

    @field_validator("chart_type")
    @classmethod
    def validate_chart_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in {"bar", "line"}:
            raise ValueError("chart_type must be one of: bar, line.")
        return normalized

    @field_validator("warning")
    @classmethod
    def normalize_warning(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_chart_shape(self) -> ChartArtifact:
        if self.chart_spec is not None and self.chart_type is None:
            raise ValueError("chart_type is required when chart_spec is present.")
        return self


class RefusalArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: RefusalCode
    category: RefusalCategory
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("refusal message cannot be empty.")
        return normalized


class GuardrailDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    refusal: RefusalArtifact | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> GuardrailDecision:
        if self.allowed and self.refusal is not None:
            raise ValueError("allowed guardrail decisions must not include a refusal.")
        if not self.allowed and self.refusal is None:
            raise ValueError("blocked guardrail decisions must include a refusal.")
        return self


class AskRequestArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    session_id: str | None = None
    user_id: str | None = None
    preview_only: bool = False

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question cannot be empty.")
        return normalized

    @field_validator("session_id", "user_id")
    @classmethod
    def normalize_optional_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SqlCandidateArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    model_generated_sql: str

    @field_validator("question", "model_generated_sql")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text fields cannot be empty.")
        return normalized


class ValidatedSqlArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    validated_sql: str
    model_generated_sql: str | None = None
    executed_sql: str | None = None
    limit_applied: bool = False
    execution_skipped: bool = False

    @field_validator("validated_sql")
    @classmethod
    def validate_validated_sql(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("validated_sql cannot be empty.")
        return normalized

    @field_validator("model_generated_sql", "executed_sql")
    @classmethod
    def normalize_optional_sql(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
