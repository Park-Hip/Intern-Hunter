import re
import json
from typing import Tuple
from src.internhunter.llm.providers import GeminiClient
from src.internhunter.config.settings import settings
from src.internhunter.common.logging import get_logger

logger = get_logger(__name__)


class JobValidator:
    def __init__(self):
        # Use lite model for cheap validation — configurable via settings.yaml
        validation_model = settings.llm.validation_model
        self.lite_client = GeminiClient(model=validation_model)
        
    @staticmethod
    def heuristic_check(text: str) -> bool:
        """Rapid check using length and keywords."""
        if not text:
            return False
            
        # Clean markdown junk
        clean_text = re.sub(r'\[.*?\]\(.*?\)', '', text) # Remove links
        
        if len(clean_text) < 300:
            logger.info("Heuristic failed: text too short", length=len(clean_text))
            return False
            
        keywords = ["mô tả", "yêu cầu", "quyền lợi", "phúc lợi", "job", "requirement", "description", "benefit", "tuyển dụng"]
        found_keywords = [k for k in keywords if k in text.lower()]
        
        if len(found_keywords) < 2:
            logger.info("Heuristic failed: not enough keywords", found=found_keywords)
            return False
            
        return True

    def validate_with_llm(self, text: str) -> Tuple[bool, str]:
        """Low-cost LLM check for validity (Captcha/Expired/Non-job detection)."""
        prompt = settings.render_prompt("job_validation", text_snippet=text[:3000])
        
        try:
            # Note: GeminiClient.client is the raw genai.Client
            response = self.lite_client.client.models.generate_content(
                model=self.lite_client.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.0
                }
            )
            
            data = json.loads(response.text)
            is_job = data.get("is_job", False)
            reason = data.get("reason", "No reason provided")
            
            if not is_job:
                logger.warning("LLM Validation rejected page", reason=reason)
            
            return is_job, reason
        except Exception as e:
            logger.error("LLM Validation failed", error=str(e))
            # Production-grade fallback: if LLM fails but heuristic passed, we let it through 
            # to Stage 3 for the main LLM to decide (safer than dropping valid jobs).
            return True, f"LLM Error: {str(e)}"

    def is_valid(self, text: str) -> Tuple[bool, str]:
        """Hybrid validation check: Heuristics first, then LLM-Lite."""
        # 1. Heuristics (Zero cost)
        if not self.heuristic_check(text):
            return False, "Heuristic check failed: text too short or lacks job keywords."
            
        # 2. LLM-Lite (Minimal cost)
        return self.validate_with_llm(text)
