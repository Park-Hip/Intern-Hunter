from google.genai import types
from tenacity import wait_exponential, retry, stop_after_attempt, retry_if_exception_type
from typing import List
from langdetect import detect

from src.internhunter.config.settings import settings
from src.internhunter.common.logging import get_logger
from src.internhunter.llm.router import llm_router
from src.internhunter.llm.providers import GEMINI_RETRY_EXCEPTIONS

logger = get_logger(__name__)

class Embedder:
    """Generates embeddings using Gemini's embedding API.
    
    Reuses the router's Gemini client to avoid creating duplicate genai.Client instances.
    Translates non-English text before embedding for consistent multilingual search.
    """

    def __init__(self):
        self.router = llm_router

    def _get_gemini_client(self):
        """Lazy access to router's Gemini client (avoids duplicate genai.Client)."""
        return self.router.get_client("gemini").client

    @retry(
        stop=stop_after_attempt(settings.crawler.max_retries),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(GEMINI_RETRY_EXCEPTIONS)
    )
    def generate_embedding(self, text: str) -> List[float]:
        try:
            lan = detect(text)
        except Exception:
            lan = "en"

        if lan != "en":
            try:
                text = self.router.translate_with_fallback(text)
            except Exception as e:
                logger.warning(f"Translation failed, using original text: {e}")

        try:
            result = self._get_gemini_client().models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY", output_dimensionality=768),
            )
            
            return result.embeddings[0].values
        except Exception as e:
            logger.error(f"Fail to generate embedding: {e}")
            raise

embedder = Embedder()
