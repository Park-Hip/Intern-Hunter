from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class TopCVCrawlerSettings(BaseModel):
    class SearchSeed(BaseModel):
        name: str
        url: str

    headless: bool = True
    enable_stealth: bool = True
    user_agent_mode: str = "random"
    use_persistent_context: bool = False
    user_data_dir: str | None = None
    storage_state_path: str | None = None
    page_timeout_ms: int = 30000
    delay_before_return_html: float = 3.0
    fetch_wait_for: str = "css:.job-item-search-result"
    wait_for: str = "css:h1, h2.title, .job-detail-title"
    screenshot: bool = True
    cache_mode: str = "bypass"
    magic: bool = True
    simulate_user: bool = True
    remove_overlay_elements: bool = False
    exclude_external_links: bool = True
    word_count_threshold: int = 5
    proxy_enabled: bool = False
    proxy_servers: list[str] = Field(
        default_factory=lambda: [
            "dc.oxylabs.io:8001",
            "dc.oxylabs.io:8002",
            "dc.oxylabs.io:8003",
            "dc.oxylabs.io:8004",
            "dc.oxylabs.io:8005",
        ]
    )
    proxy_rotation: str = "round_robin"
    proxy_username_env: str = "OXYLABS_USERNAME"
    proxy_password_env: str = "OXYLABS_PASSWORD"
    detail_delay_min_seconds: float = 2.0
    detail_delay_max_seconds: float = 5.0
    blocked_delay_min_seconds: float = 8.0
    blocked_delay_max_seconds: float = 15.0
    blocked_early_stop_threshold: int = 2
    blocked_cooldown_minutes: int = 60
    search_seeds: list[SearchSeed] = Field(default_factory=list)


class CrawlerSettings(BaseModel):
    rate_limit_rpm: int = 20
    max_retries: int = 3
    max_pages: int = 5
    extract_delay_min: float = 10.0
    extract_delay_max: float = 15.0
    topcv: TopCVCrawlerSettings = Field(default_factory=TopCVCrawlerSettings)


class AgentSettings(BaseModel):
    max_iterations: int = 5
    memory_limit: int = 10
    default_query_limit: int = 50
    max_query_limit: int = 100


class Settings(BaseSettings):
    GEMINI_API_KEY: SecretStr | None = None
    GROQ_API_KEY: SecretStr | None = None
    DB_URL: SecretStr | None = None
    DS_URL: str = "https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1"
    AIE_URL: str = "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1"

    APP_NAME: str = "job-finder"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    BASE_DIR: Path = Path(__file__).resolve().parents[3]

    crawler: CrawlerSettings = Field(default_factory=CrawlerSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    config_yaml: Dict[str, Any] = {}
    prompts_yaml: Dict[str, Any] = {}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    @property
    def search_urls(self) -> list[str]:
        # Prefer configured TopCV search seeds from settings.yaml when present.
        seed_urls = [seed.url for seed in self.crawler.topcv.search_seeds if seed.url]
        if seed_urls:
            return seed_urls

        # Backward-compatible fallback for older configs that still rely on the
        # legacy hard-coded TopCV seed constants.
        return [self.AIE_URL, self.DS_URL]

    def get_prompt(self, name: str) -> str:
        return self.prompts_yaml.get("prompts", {}).get(name, "")

    def render_prompt(self, name: str, **context: Any) -> str:
        template = self.get_prompt(name)
        if not template:
            return ""

        from jinja2 import Template

        return Template(template).render(**context)


def load_settings() -> Settings:
    loaded = Settings()

    config_path = loaded.BASE_DIR / "src" / "config" / "settings.yaml"
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            config_yaml = yaml.safe_load(f) or {}
            loaded.config_yaml = config_yaml
            if "crawler" in config_yaml:
                loaded.crawler = CrawlerSettings(**config_yaml["crawler"])
            if "agent" in config_yaml:
                loaded.agent = AgentSettings(**config_yaml["agent"])

    prompts_path = loaded.BASE_DIR / "src" / "config" / "prompts.yaml"
    if prompts_path.exists():
        with prompts_path.open("r", encoding="utf-8") as f:
            loaded.prompts_yaml = yaml.safe_load(f) or {}

    return loaded


settings = load_settings()

__all__ = ["AgentSettings", "CrawlerSettings", "Settings", "TopCVCrawlerSettings", "load_settings", "settings"]
