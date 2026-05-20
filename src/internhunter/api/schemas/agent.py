from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.agents.types import (
    ChartArtifact,
    RefusalArtifact,
    TableArtifact,
)


class AgentResponseStatus:
    OK = "ok"
    REFUSED = "refused"


class AgentAskRequest(BaseModel):
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


class AgentSQLPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_generated_sql: str | None = None
    validated_sql: str | None = None
    executed_sql: str | None = None

    @field_validator("model_generated_sql", "validated_sql", "executed_sql")
    @classmethod
    def normalize_optional_sql(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AgentResponseMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit_applied: bool = False
    execution_skipped: bool = False
    trace_id: str
    session_id: str | None = None
    user_id: str | None = None

    @field_validator("trace_id")
    @classmethod
    def validate_trace_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("trace_id cannot be empty.")
        return normalized

    @field_validator("session_id", "user_id")
    @classmethod
    def normalize_optional_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AgentErrorPayload(RefusalArtifact):
    pass


class AgentAskResponseBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "refused"]
    question: str
    sql: AgentSQLPayload = Field(default_factory=AgentSQLPayload)
    table: TableArtifact | None = None
    summary: str | None = None
    chart: ChartArtifact | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: AgentResponseMetadata
    error: AgentErrorPayload | None = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("question cannot be empty.")
        return normalized

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("warnings")
    @classmethod
    def normalize_warnings(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for warning in value:
            item = warning.strip()
            if item:
                normalized.append(item)
        return normalized


class AgentAskOkResponse(AgentAskResponseBase):
    status: Literal["ok"] = AgentResponseStatus.OK
    error: None = None


class AgentAskPreviewResponse(AgentAskOkResponse):
    @model_validator(mode="after")
    def validate_preview_shape(self) -> AgentAskPreviewResponse:
        if self.table is not None:
            raise ValueError("preview responses must not include table results.")
        if self.chart is not None:
            raise ValueError("preview responses must not include chart results.")
        if self.sql.validated_sql is None:
            raise ValueError("preview responses must include validated_sql.")
        if self.sql.executed_sql is not None:
            raise ValueError("preview responses must not include executed_sql.")
        if not self.metadata.execution_skipped:
            raise ValueError("preview responses must set execution_skipped to true.")
        return self


class AgentAskRefusedResponse(AgentAskResponseBase):
    status: Literal["refused"] = AgentResponseStatus.REFUSED
    error: AgentErrorPayload

    @model_validator(mode="after")
    def validate_refused_shape(self) -> AgentAskRefusedResponse:
        if self.table is not None:
            raise ValueError("refused responses must not include table results.")
        if self.chart is not None:
            raise ValueError("refused responses must not include chart results.")
        if self.sql.executed_sql is not None:
            raise ValueError("refused responses must not include executed_sql.")
        if not self.metadata.execution_skipped:
            raise ValueError("refused responses must set execution_skipped to true.")
        return self


AgentAskResponse: TypeAlias = AgentAskOkResponse | AgentAskPreviewResponse | AgentAskRefusedResponse
