from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from src.agents.memory import AgentMemoryMessage, AgentMemoryStore
from src.agents.state import AgentRuntimeInput, AgentRuntimeOutput
from src.agents.tracing import build_langchain_tracing_config, get_current_trace_id_or_fallback
from src.internhunter.config.settings import settings

if TYPE_CHECKING:
    from src.agents.provider import AgentProvider


class AgentGraph(Protocol):
    """Protocol for the compiled LangChain agent graph."""

    def invoke(
        self,
        payload: dict[str, Any],
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Invoke the compiled graph with a LangChain agent payload and config."""


class AgentRuntime:
    """Small wrapper around the Milestone 1 LangChain agent runtime."""

    def __init__(
        self,
        agent: AgentGraph,
        memory: AgentMemoryStore | None = None,
    ) -> None:
        """Store the compiled agent graph and optional memory seam."""
        self.agent = agent
        self.memory = memory or AgentMemoryStore()

    def invoke(self, payload: AgentRuntimeInput) -> AgentRuntimeOutput:
        """Invoke the graph and translate its output into a typed runtime result."""
        messages = self._build_messages(payload)
        invocation_payload: dict[str, Any] = {"messages": messages}
        invocation_config = _merge_agent_configs(
            self.memory.build_invocation_config(payload.session_id),
            build_langchain_tracing_config(
                user_id=payload.user_id,
                session_id=payload.session_id,
            ),
        )
        response = self.agent.invoke(invocation_payload, config=invocation_config or None)
        answer = _extract_last_assistant_message(response)
        self._record_memory(payload, answer)
        return AgentRuntimeOutput(
            answer=answer,
            warnings=[],
            trace_id=get_current_trace_id_or_fallback(invocation_config),
        )

    def _build_messages(self, payload: AgentRuntimeInput) -> list[AgentMemoryMessage]:
        """Build the user-facing message list, including short session history."""
        messages: list[AgentMemoryMessage] = []
        if payload.session_id:
            messages.extend(self.memory.get(payload.session_id))
        messages.append({"role": "user", "content": payload.question})
        return messages

    def _record_memory(self, payload: AgentRuntimeInput, answer: str) -> None:
        """Persist the latest exchange when the request belongs to a session."""
        if payload.session_id is None:
            return
        self.memory.append(payload.session_id, "user", payload.question)
        self.memory.append(payload.session_id, "assistant", answer)


def _extract_last_assistant_message(response: dict[str, Any]) -> str:
    """Return the last assistant message content from a graph response."""
    messages = response.get("messages", [])
    for message in reversed(messages):
        role = _message_role(message)
        if role == "assistant":
            content = _message_content(message)
            if content:
                return content

    raise ValueError("Agent runtime did not return an assistant message.")


def _message_role(message: Any) -> str | None:
    """Read a message role from either a dict or LangChain message object."""
    if isinstance(message, dict):
        return message.get("role")

    message_type = getattr(message, "type", None)
    if isinstance(message_type, str):
        return "assistant" if message_type == "ai" else message_type

    return None


def _message_content(message: Any) -> str:
    """Read plain-text content from either a dict or LangChain message object."""
    content: Any
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        return " ".join(part.strip() for part in text_parts if isinstance(part, str) and part.strip())

    return str(content).strip()


def _merge_agent_configs(*configs: dict[str, Any]) -> dict[str, Any]:
    """Merge LangGraph memory config and Langfuse callback config for one invocation."""
    merged: dict[str, Any] = {}
    for config in configs:
        if not config:
            continue
        for key, value in config.items():
            if key == "callbacks":
                callbacks = merged.setdefault("callbacks", [])
                callbacks.extend(value)
                continue
            if key == "metadata":
                metadata = merged.setdefault("metadata", {})
                metadata.update(value)
                continue
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                existing = merged[key]
                existing.update(value)
                continue
            merged[key] = value
    return merged


def build_agent_runtime(
    provider: AgentProvider | None = None,
    agent_factory: Any | None = None,
    memory: AgentMemoryStore | None = None,
) -> AgentRuntime:
    """Build the Milestone 1 runtime using the real LangChain entrypoint."""
    from langchain.agents import create_agent
    from src.agents.provider import AgentProvider

    model_provider = provider or AgentProvider()
    memory_limit = getattr(getattr(model_provider, "settings", None), "agent", None)
    configured_limit = getattr(memory_limit, "memory_limit", 10)
    runtime_memory = memory or AgentMemoryStore(limit=configured_limit)
    model = model_provider.build_model()
    builder = agent_factory or create_agent
    agent = builder(
        model=model,
        tools=[],
        system_prompt=_load_agent_system_prompt(),
    )
    return AgentRuntime(agent=agent, memory=runtime_memory)


def _load_agent_system_prompt() -> str:
    """Load the runtime system prompt from YAML-backed settings."""
    prompt = settings.get_prompt("agent_runtime_system") or settings.get_prompt("agent_system")
    if prompt.strip():
        return prompt

    return (
        "You are the InternHunter database agent runtime. "
        "You are in Milestone 1 with no tools available. "
        "Stay within the job-database assistant scope, answer briefly, "
        "and never claim to execute SQL or inspect live database results."
    )
