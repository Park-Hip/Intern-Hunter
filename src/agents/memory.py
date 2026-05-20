from __future__ import annotations

from collections import defaultdict
from typing import TypedDict


class AgentMemoryMessage(TypedDict):
    """Simple message payload stored in short-term agent memory."""

    role: str
    content: str


class AgentMemoryStore:
    """Bounded in-process short-memory store keyed by session id."""

    def __init__(self, limit: int = 10) -> None:
        """Create a store that keeps only the most recent messages per session."""
        self.limit = limit
        self._messages: dict[str, list[AgentMemoryMessage]] = defaultdict(list)

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session history and enforce the retention limit."""
        history = self._messages[session_id]
        history.append({"role": role, "content": content})
        self._messages[session_id] = history[-self.limit :]

    def get(self, session_id: str) -> list[AgentMemoryMessage]:
        """Return a copy of the stored message history for one session."""
        return list(self._messages.get(session_id, []))

    def build_invocation_config(self, session_id: str | None) -> dict[str, dict[str, str]]:
        """Return a LangGraph-style thread config for future checkpointer compatibility."""
        if session_id is None:
            return {}
        return {"configurable": {"thread_id": session_id}}
