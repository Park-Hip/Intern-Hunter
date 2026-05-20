import json

from src.core.models import ProcessedJob, LLMJobProcess, RawJob
from src.internhunter.config.settings import settings
from src.internhunter.common.logging import get_logger
from src.internhunter.llm.base import LLMProvider

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from google import genai
from google.genai import types
from groq import Groq

logger = get_logger(__name__)

# Transient exceptions worth retrying (NOT validation/parse errors)
_base_retry = (ConnectionError, TimeoutError)

try:
    from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, DeadlineExceeded
    GEMINI_RETRY_EXCEPTIONS = _base_retry + (ResourceExhausted, ServiceUnavailable, DeadlineExceeded)
except ImportError:
    GEMINI_RETRY_EXCEPTIONS = _base_retry

GROQ_RETRY_EXCEPTIONS = _base_retry

# Try to add Groq-specific transient exceptions
try:
    from groq import RateLimitError as GroqRateLimitError, APIConnectionError as GroqAPIConnectionError
    GROQ_RETRY_EXCEPTIONS = GROQ_RETRY_EXCEPTIONS + (GroqRateLimitError, GroqAPIConnectionError)
except ImportError:
    pass

try:
    import mlflow
    if settings.mlflow.tracking_uri:
        mlflow.set_tracking_uri(settings.mlflow.tracking_uri)
    if settings.mlflow.experiment:
        mlflow.set_experiment(settings.mlflow.experiment)
    _mlflow_available = True
except ImportError:
    _mlflow_available = False
    logger.info("MLflow not available, skipping autolog setup.")


def _load_prompt(prompt_name: str = "job_processor"):
    """Load prompt template from centralized settings."""
    return settings.get_prompt(prompt_name)


def _build_prompt(prompt_template, job_data: RawJob, raw_context: dict, description, requirement, benefit, work_location=None, working_time=None, application_method=None):
    """Build the final prompt string from template or fallback."""
    if prompt_template:
        from jinja2 import Template
        template = Template(prompt_template)
        return template.render(
            title=job_data.title or "",
            company=job_data.company or "",
            location=job_data.location or "",
            salary=raw_context.get("salary", ""),
            experience=raw_context.get("experience", ""),
            description=description,
            requirement=requirement,
            benefit=benefit,
            work_location=work_location or "",
            working_time=working_time or "",
            application_method=application_method or "",
        )
    else:
        return f"""
        Extract job details for position: {job_data.title} at {job_data.company}.
        Location: {job_data.location}
        Raw Data: {raw_context}
        """


def _render_named_prompt(prompt_name: str, **context) -> str:
    """Render a named prompt template from prompts.yaml."""
    return settings.render_prompt(prompt_name, **context)

# ============================================================
# Gemini Provider
# ============================================================
class GeminiClient(LLMProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.api_key = api_key or (
            settings.GEMINI_API_KEY.get_secret_value() if settings.GEMINI_API_KEY else None
        )
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment or passed to constructor.")

        cfg = settings.llm.gemini
        self.model = model or cfg.model
        self.temperature = cfg.temperature
        self.max_tokens = cfg.max_tokens
        
        self.client = genai.Client(api_key=self.api_key)
        if _mlflow_available:
            try:
                mlflow.gemini.autolog()
            except Exception as e:
                logger.warning("MLflow autolog setup failed", error=str(e))

    @retry(
        stop=stop_after_attempt(settings.crawler.max_retries),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(GEMINI_RETRY_EXCEPTIONS)
    )
    def process_raw_job(self, job_data: RawJob) -> ProcessedJob:
        """Generates structured job data from raw dictionary using Gemini."""
        raw_context, description, requirement, benefit, work_location, working_time, application_method = self._prepare_job_context(job_data)

        prompt_template = _load_prompt(prompt_name="job_processor")
        job_processor_prompt = _build_prompt(
            prompt_template,
            job_data,
            raw_context,
            description,
            requirement,
            benefit,
            work_location=work_location,
            working_time=working_time,
            application_method=application_method,
        )

        result = self.client.models.generate_content(
            model=self.model,
            contents=job_processor_prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=LLMJobProcess,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens
            )
        )

        if result.parsed:
            processed_job = ProcessedJob(
                **result.parsed.dict(),
                description=description,
                requirement=requirement,
                benefit=benefit,
            )
            return processed_job
        else:
            raise ValueError("Model returned no parsed result.")

    @retry(
        stop=stop_after_attempt(settings.crawler.max_retries),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(GEMINI_RETRY_EXCEPTIONS)
    )
    def translate(self, text: str) -> str:
        """Translate text to English using Gemini."""
        try:
            result = self.client.models.generate_content(
                model=self.model,
                contents=_render_named_prompt("translate_to_english", text=text),
            )
            return result.text.strip()
        except Exception as e:
            logger.error("Translation failed", error=str(e))
            raise


# ============================================================
# Groq Provider
# ============================================================
class GroqClient(LLMProvider):
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or (
            settings.GROQ_API_KEY.get_secret_value() if settings.GROQ_API_KEY else None
        )
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set in environment or passed to constructor.")
        
        cfg = settings.llm.groq
        self.model = model or cfg.model
        self.temperature = cfg.temperature
        self.max_tokens = cfg.max_tokens
        
        self.client = Groq(api_key=self.api_key)

    @retry(
        stop=stop_after_attempt(settings.crawler.max_retries),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(GROQ_RETRY_EXCEPTIONS)
    )
    def process_raw_job(self, job_data: RawJob) -> ProcessedJob:
        """Generates structured job data from raw dictionary using Groq."""
        raw_context, description, requirement, benefit, work_location, working_time, application_method = self._prepare_job_context(job_data)

        prompt_template = _load_prompt(prompt_name="job_processor")
        job_processor_prompt = _build_prompt(
            prompt_template,
            job_data,
            raw_context,
            description,
            requirement,
            benefit,
            work_location=work_location,
            working_time=working_time,
            application_method=application_method,
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _load_prompt("job_processor_system")},
                {"role": "user", "content": job_processor_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "job_process",
                    "schema": LLMJobProcess.model_json_schema()
                }
            },
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )

        result = json.loads(response.choices[0].message.content)

        if result:
            processed_job = ProcessedJob(
                **result,
                description=description,
                requirement=requirement,
                benefit=benefit,
            )
            return processed_job
        else:
            raise ValueError("Model returned no parsed result.")

    @retry(
        stop=stop_after_attempt(settings.crawler.max_retries),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(GROQ_RETRY_EXCEPTIONS)
    )
    def translate(self, text: str) -> str:
        """Translate text to English using Groq."""
        try:
            result = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _load_prompt("translate_to_english_system")},
                    {"role": "user", "content": text},
                ]
            )
            return result.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Translation failed", error=str(e))
            raise
