from __future__ import annotations

from src.agents.state import AgentRuntimeInput, AgentRuntimeOutput
from src.agents.types import (
    AskRequestArtifact,
    ChartArtifact,
    GuardrailDecision,
    RefusalArtifact,
    RefusalCategory,
    RefusalCode,
    SqlCandidateArtifact,
    SummaryArtifact,
    TableArtifact,
    ValidatedSqlArtifact,
)

__all__ = [
    "handle_agent_ask",
    "AgentRuntime",
    "AgentRuntimeInput",
    "AgentRuntimeOutput",
    "AskRequestArtifact",
    "build_agent_runtime",
    "ChartArtifact",
    "GuardrailDecision",
    "RefusalArtifact",
    "RefusalCategory",
    "RefusalCode",
    "SqlCandidateArtifact",
    "SummaryArtifact",
    "TableArtifact",
    "ValidatedSqlArtifact",
]


def __getattr__(name: str):
    if name == "handle_agent_ask":
        from src.agents.service import handle_agent_ask

        return handle_agent_ask

    if name in {"AgentRuntime", "build_agent_runtime"}:
        from src.agents.runtime import AgentRuntime, build_agent_runtime

        return {"AgentRuntime": AgentRuntime, "build_agent_runtime": build_agent_runtime}[name]

    raise AttributeError(f"module 'src.agents' has no attribute {name!r}")
