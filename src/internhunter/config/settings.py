from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]
SETTINGS_YAML_PATH = BASE_DIR / "src" / "config" / "settings.yaml"
PROMPTS_YAML_PATH = BASE_DIR / "src" / "config" / "prompts.yaml"


def _read_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


SETTINGS_YAML_DEFAULTS = _read_yaml_file(SETTINGS_YAML_PATH)


def _default(path: str) -> Any:
    current: Any = SETTINGS_YAML_DEFAULTS
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            raise RuntimeError(f"Missing required settings.yaml default for '{path}'.")
        current = current[key]
    return deepcopy(current)


class AppSettings(BaseModel):
    name: str = Field(default_factory=lambda: _default("app.name"))
    version: str = Field(default_factory=lambda: _default("app.version"))
    environment: str = Field(default_factory=lambda: _default("app.environment"))


class TopCVCrawlerSettings(BaseModel):
    class SearchSeed(BaseModel):
        name: str
        url: str

    headless: bool = Field(default_factory=lambda: _default("crawler.topcv.headless"))
    enable_stealth: bool = Field(default_factory=lambda: _default("crawler.topcv.enable_stealth"))
    user_agent_mode: str = Field(default_factory=lambda: _default("crawler.topcv.user_agent_mode"))
    use_persistent_context: bool = Field(default_factory=lambda: _default("crawler.topcv.use_persistent_context"))
    user_data_dir: str | None = Field(default_factory=lambda: _default("crawler.topcv.user_data_dir"))
    storage_state_path: str | None = Field(default_factory=lambda: _default("crawler.topcv.storage_state_path"))
    page_timeout_ms: int = Field(default_factory=lambda: _default("crawler.topcv.page_timeout_ms"))
    delay_before_return_html: float = Field(default_factory=lambda: _default("crawler.topcv.delay_before_return_html"))
    fetch_wait_for: str = Field(default_factory=lambda: _default("crawler.topcv.fetch_wait_for"))
    wait_for: str = Field(default_factory=lambda: _default("crawler.topcv.wait_for"))
    screenshot: bool = Field(default_factory=lambda: _default("crawler.topcv.screenshot"))
    cache_mode: str = Field(default_factory=lambda: _default("crawler.topcv.cache_mode"))
    magic: bool = Field(default_factory=lambda: _default("crawler.topcv.magic"))
    simulate_user: bool = Field(default_factory=lambda: _default("crawler.topcv.simulate_user"))
    remove_overlay_elements: bool = Field(default_factory=lambda: _default("crawler.topcv.remove_overlay_elements"))
    exclude_external_links: bool = Field(default_factory=lambda: _default("crawler.topcv.exclude_external_links"))
    word_count_threshold: int = Field(default_factory=lambda: _default("crawler.topcv.word_count_threshold"))
    proxy_enabled: bool = Field(default_factory=lambda: _default("crawler.topcv.proxy_enabled"))
    proxy_servers: list[str] = Field(default_factory=lambda: _default("crawler.topcv.proxy_servers"))
    proxy_rotation: str = Field(default_factory=lambda: _default("crawler.topcv.proxy_rotation"))
    proxy_username_env: str = Field(default_factory=lambda: _default("crawler.topcv.proxy_username_env"))
    proxy_password_env: str = Field(default_factory=lambda: _default("crawler.topcv.proxy_password_env"))
    detail_delay_min_seconds: float = Field(default_factory=lambda: _default("crawler.topcv.detail_delay_min_seconds"))
    detail_delay_max_seconds: float = Field(default_factory=lambda: _default("crawler.topcv.detail_delay_max_seconds"))
    blocked_delay_min_seconds: float = Field(default_factory=lambda: _default("crawler.topcv.blocked_delay_min_seconds"))
    blocked_delay_max_seconds: float = Field(default_factory=lambda: _default("crawler.topcv.blocked_delay_max_seconds"))
    blocked_early_stop_threshold: int = Field(default_factory=lambda: _default("crawler.topcv.blocked_early_stop_threshold"))
    blocked_cooldown_minutes: int = Field(default_factory=lambda: _default("crawler.topcv.blocked_cooldown_minutes"))
    search_seeds: list[SearchSeed] = Field(
        default_factory=lambda: [
            TopCVCrawlerSettings.SearchSeed.model_validate(seed)
            for seed in _default("crawler.topcv.search_seeds")
        ]
    )


class CrawlerSettings(BaseModel):
    rate_limit_rpm: int = Field(default_factory=lambda: _default("crawler.rate_limit_rpm"))
    max_retries: int = Field(default_factory=lambda: _default("crawler.max_retries"))
    max_pages: int = Field(default_factory=lambda: _default("crawler.max_pages"))
    extract_delay_min: float = Field(default_factory=lambda: _default("crawler.extract_delay_min"))
    extract_delay_max: float = Field(default_factory=lambda: _default("crawler.extract_delay_max"))
    topcv: TopCVCrawlerSettings = Field(default_factory=TopCVCrawlerSettings)


class AgentProviderSettings(BaseModel):
    name: str = Field(default_factory=lambda: _default("agent.provider.name"))
    model: str = Field(default_factory=lambda: _default("agent.provider.model"))
    base_url: str = Field(default_factory=lambda: _default("agent.provider.base_url"))
    temperature: float = Field(default_factory=lambda: _default("agent.provider.temperature"))


class AgentSettings(BaseModel):
    max_iterations: int = Field(default_factory=lambda: _default("agent.max_iterations"))
    memory_limit: int = Field(default_factory=lambda: _default("agent.memory_limit"))
    default_query_limit: int = Field(default_factory=lambda: _default("agent.default_query_limit"))
    max_query_limit: int = Field(default_factory=lambda: _default("agent.max_query_limit"))
    provider: AgentProviderSettings = Field(default_factory=AgentProviderSettings)


class LLMProviderSettings(BaseModel):
    model: str
    temperature: float
    max_tokens: int


class LLMSettings(BaseModel):
    primary_provider: str = Field(default_factory=lambda: _default("llm.primary_provider"))
    fallback_provider: str = Field(default_factory=lambda: _default("llm.fallback_provider"))
    validation_model: str = Field(default_factory=lambda: _default("llm.validation_model"))
    rate_limit_rpm: int = Field(default_factory=lambda: _default("llm.rate_limit_rpm"))
    gemini: LLMProviderSettings = Field(default_factory=lambda: LLMProviderSettings.model_validate(_default("llm.gemini")))
    groq: LLMProviderSettings = Field(default_factory=lambda: LLMProviderSettings.model_validate(_default("llm.groq")))


class LoggingSettings(BaseModel):
    format: str = Field(default_factory=lambda: _default("logging.format"))
    level: str = Field(default_factory=lambda: _default("logging.level"))


class MLflowSettings(BaseModel):
    tracking_uri: str = Field(default_factory=lambda: _default("mlflow.tracking_uri"))
    experiment: str = Field(default_factory=lambda: _default("mlflow.experiment"))


class Settings(BaseSettings):
    GEMINI_API_KEY: SecretStr | None = None
    GROQ_API_KEY: SecretStr | None = None
    DB_URL: SecretStr | None = None
    POSTGRES_PASSWORD: SecretStr | None = None
    LANGFUSE_PUBLIC_KEY: SecretStr | None = None
    LANGFUSE_SECRET_KEY: SecretStr | None = None
    LANGFUSE_HOST: str | None = None

    APP_NAME: str | None = None
    APP_VERSION: str | None = None
    ENVIRONMENT: str | None = None
    MLFLOW_TRACKING_URI: str | None = None
    MLFLOW_EXPERIMENT: str | None = None

    BASE_DIR: Path = BASE_DIR
    app: AppSettings = Field(default_factory=AppSettings)
    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    mlflow: MLflowSettings = Field(default_factory=MLflowSettings)
    prompts_yaml: dict[str, Any] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    @property
    def search_urls(self) -> list[str]:
        return [seed.url for seed in self.crawler.topcv.search_seeds if seed.url]

    def get_prompt(self, name: str) -> str:
        return self.prompts_yaml.get("prompts", {}).get(name, "")

    def render_prompt(self, name: str, **context: Any) -> str:
        template = self.get_prompt(name)
        if not template:
            return ""

        from jinja2 import Template

        return Template(template).render(**context)


def _apply_env_overrides(loaded: Settings) -> Settings:
    loaded.app.name = loaded.APP_NAME or loaded.app.name
    loaded.APP_NAME = loaded.app.name

    loaded.app.version = loaded.APP_VERSION or loaded.app.version
    loaded.APP_VERSION = loaded.app.version

    loaded.app.environment = loaded.ENVIRONMENT or loaded.app.environment
    loaded.ENVIRONMENT = loaded.app.environment

    loaded.mlflow.tracking_uri = loaded.MLFLOW_TRACKING_URI or loaded.mlflow.tracking_uri
    loaded.MLFLOW_TRACKING_URI = loaded.mlflow.tracking_uri

    loaded.mlflow.experiment = loaded.MLFLOW_EXPERIMENT or loaded.mlflow.experiment
    loaded.MLFLOW_EXPERIMENT = loaded.mlflow.experiment

    return loaded


def load_settings() -> Settings:
    loaded = Settings()
    loaded = _apply_env_overrides(loaded)
    loaded.prompts_yaml = _read_yaml_file(PROMPTS_YAML_PATH)
    return loaded


settings = load_settings()

__all__ = [
    "AgentProviderSettings",
    "AgentSettings",
    "AppSettings",
    "CrawlerSettings",
    "LLMProviderSettings",
    "LLMSettings",
    "LoggingSettings",
    "MLflowSettings",
    "Settings",
    "TopCVCrawlerSettings",
    "load_settings",
    "settings",
]
