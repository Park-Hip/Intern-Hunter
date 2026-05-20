from __future__ import annotations

from langchain_ollama import ChatOllama


def test_agent_provider_build_model_returns_chat_ollama() -> None:
    """The provider seam should build the real local chat model."""
    from src.agents.provider import AgentProvider

    provider = AgentProvider()

    model = provider.build_model()

    assert isinstance(model, ChatOllama)
    assert model.model == "qwen3.5:4b"
    assert model.base_url == "http://127.0.0.1:11434"
