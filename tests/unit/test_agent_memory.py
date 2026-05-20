from __future__ import annotations

from src.agents.memory import AgentMemoryStore


def test_memory_store_round_trips_session_history() -> None:
    """The memory store should preserve message order within a session."""
    store = AgentMemoryStore()

    store.append("session-1", "user", "hello")
    store.append("session-1", "assistant", "hi there")

    history = store.get("session-1")

    assert len(history) == 2
    assert history[0]["content"] == "hello"
    assert history[1]["content"] == "hi there"


def test_memory_store_applies_bounded_history_limit() -> None:
    """The store should keep only the most recent messages for a session."""
    store = AgentMemoryStore(limit=2)

    store.append("session-1", "user", "first")
    store.append("session-1", "assistant", "second")
    store.append("session-1", "user", "third")

    assert store.get("session-1") == [
        {"role": "assistant", "content": "second"},
        {"role": "user", "content": "third"},
    ]
