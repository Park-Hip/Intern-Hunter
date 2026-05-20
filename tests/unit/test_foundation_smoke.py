from src.internhunter.common.logging import (
    configure_logging as new_configure_logging,
    get_logger as new_get_logger,
)
from src.internhunter.config.settings import settings as new_settings
from src.internhunter.common.logging import (
    configure_logging as canonical_configure_logging,
    get_logger as canonical_get_logger,
)
from src.internhunter.common.logging import (
    configure_logging as legacy_configure_logging,
    get_logger as legacy_get_logger,
)
from src.internhunter.config.settings import settings as legacy_settings


def test_foundation_modules_import():
    logger = new_get_logger(__name__)

    assert logger is not None
    assert new_settings is legacy_settings
    assert new_settings.APP_NAME == "job-finder"
    assert new_settings.APP_VERSION == "2.0.0"
    assert new_settings.ENVIRONMENT == "development"
    assert new_settings.llm.primary_provider == "gemini"
    assert new_settings.logging.level == "INFO"
    assert new_settings.mlflow.experiment == "job-finder"
    assert isinstance(new_settings.search_urls, list)
    assert len(new_settings.search_urls) == 2
    assert new_settings.search_urls[0].endswith("ai-engineer?sba=1")
    assert new_settings.crawler.topcv.headless is False
    assert new_settings.crawler.topcv.enable_stealth is True
    assert new_settings.crawler.topcv.user_agent_mode == "random"
    assert new_settings.crawler.topcv.use_persistent_context is False
    assert new_settings.crawler.topcv.page_timeout_ms == 60000
    assert new_settings.crawler.topcv.delay_before_return_html == 5.0
    assert new_settings.crawler.topcv.fetch_wait_for == "css:.job-item-search-result"
    assert new_settings.crawler.topcv.screenshot is False
    assert new_settings.crawler.topcv.cache_mode == "bypass"
    assert new_settings.crawler.topcv.magic is True
    assert new_settings.crawler.topcv.simulate_user is True
    assert new_settings.crawler.topcv.remove_overlay_elements is False
    assert new_settings.crawler.topcv.exclude_external_links is True
    assert new_settings.crawler.topcv.word_count_threshold == 5
    assert new_settings.crawler.max_retries == 2
    assert new_settings.crawler.topcv.blocked_early_stop_threshold == 1
    assert new_settings.crawler.topcv.blocked_cooldown_minutes == 180
    assert legacy_get_logger is new_get_logger
    assert canonical_get_logger is new_get_logger
    assert legacy_configure_logging is new_configure_logging
    assert canonical_configure_logging is new_configure_logging
