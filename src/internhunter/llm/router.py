from typing import Literal

from src.internhunter.llm.providers import GeminiClient, GroqClient
from src.internhunter.llm.base import LLMProvider
from src.core.models import ProcessedJob, RawJob
from src.internhunter.common.logging import get_logger

logger = get_logger(__name__)


class LLMRouter:
    """
    Routes requests to the appropriate LLM provider.
    Supports automatic fallback: Gemini (primary) -> Groq (fallback).
    """

    def __init__(self):
        self._gemini: GeminiClient | None = None
        self._groq: GroqClient | None = None

    def get_client(self, provider: Literal["gemini", "groq"] = "gemini") -> LLMProvider:
        """Get a specific LLM provider client (lazy-initialized)."""
        if provider == "gemini":
            if not self._gemini:
                self._gemini = GeminiClient()
            return self._gemini
        elif provider == "groq":
            if not self._groq:
                self._groq = GroqClient()
            return self._groq

        raise ValueError(f"Unknown provider: {provider}")

    def process_with_fallback(self, job_data: RawJob) -> ProcessedJob:
        """
        Try Gemini first. On failure, fall back to Groq.
        """
        try:
            client = self.get_client("gemini")
            return client.process_raw_job(job_data)
        except Exception as e:
            logger.warning(
                "Gemini failed, falling back to Groq",
                error=str(e),
            )
            try:
                client = self.get_client("groq")
                return client.process_raw_job(job_data)
            except Exception as fallback_error:
                logger.error(
                    "Both Gemini and Groq failed",
                    gemini_error=str(e),
                    groq_error=str(fallback_error),
                )
                raise fallback_error

    def translate_with_fallback(self, text: str) -> str:
        """
        Try Gemini for translation first. On failure, fall back to Groq.
        """
        try:
            client = self.get_client("gemini")
            return client.translate(text)
        except Exception as e:
            logger.warning(
                "Gemini translation failed, falling back to Groq",
                error=str(e),
            )
            try:
                client = self.get_client("groq")
                return client.translate(text)
            except Exception as fallback_error:
                logger.error(
                    "Both providers failed for translation",
                    gemini_error=str(e),
                    groq_error=str(fallback_error),
                )
                raise fallback_error


# Singleton router
llm_router = LLMRouter()
