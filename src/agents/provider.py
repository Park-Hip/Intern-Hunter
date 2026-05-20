from __future__ import annotations

from langchain_ollama import ChatOllama

from src.internhunter.config.settings import AgentProviderSettings, Settings, load_settings


class AgentProvider:
    """Builds the chat model used by the agent runtime."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Load shared settings and resolve provider-specific defaults."""
        self.settings = settings or load_settings()
        self.provider_settings = AgentProviderSettings.model_validate(self.settings.agent.provider.model_dump())

    def build_model(self) -> ChatOllama:
        """Create the Ollama chat model without forcing remote validation."""
        if self.provider_settings.name.lower() != "ollama":
            raise ValueError("Milestone 1 only supports the Ollama agent provider.")

        return ChatOllama(
            model=self.provider_settings.model,
            base_url=self.provider_settings.base_url,
            temperature=self.provider_settings.temperature,
            validate_model_on_init=False,
        )
