import hashlib

import pytest
from crawl4ai.async_configs import CacheMode

from src.internhunter.config.settings import CrawlerSettings, Settings, TopCVCrawlerSettings
from src.internhunter.crawler import crawl_config


def test_topcv_crawler_config_builders_use_settings_values(monkeypatch):
    topcv = crawl_config.settings.crawler.topcv

    monkeypatch.setattr(topcv, "headless", False)
    monkeypatch.setattr(topcv, "enable_stealth", False)
    monkeypatch.setattr(topcv, "user_agent_mode", "random")
    monkeypatch.setattr(topcv, "use_persistent_context", True)
    monkeypatch.setattr(topcv, "user_data_dir", "C:/tmp/topcv-profile")
    monkeypatch.setattr(topcv, "storage_state_path", "C:/tmp/topcv-state.json")
    monkeypatch.setattr(topcv, "page_timeout_ms", 45000)
    monkeypatch.setattr(topcv, "delay_before_return_html", 4.5)
    monkeypatch.setattr(topcv, "fetch_wait_for", "css:.custom-listing-ready")
    monkeypatch.setattr(topcv, "wait_for", "css:.custom-ready")
    monkeypatch.setattr(topcv, "screenshot", False)
    monkeypatch.setattr(topcv, "cache_mode", "enabled")
    monkeypatch.setattr(topcv, "magic", False)
    monkeypatch.setattr(topcv, "simulate_user", False)
    monkeypatch.setattr(topcv, "remove_overlay_elements", True)
    monkeypatch.setattr(topcv, "exclude_external_links", False)
    monkeypatch.setattr(topcv, "word_count_threshold", 9)
    monkeypatch.setattr(crawl_config.settings.crawler, "max_retries", 7)

    browser_config = crawl_config.build_browser_config()
    fetch_config = crawl_config.build_fetch_link_run_config(session_id="topcv-run-1")
    detail_config = crawl_config.build_extract_detail_run_config(session_id="topcv-run-1")

    assert browser_config.headless is False
    assert browser_config.enable_stealth is False
    assert browser_config.user_agent_mode == "random"
    assert browser_config.use_persistent_context is True
    assert browser_config.user_data_dir == "C:/tmp/topcv-profile"
    assert getattr(browser_config, "storage_state", None) == "C:/tmp/topcv-state.json"
    assert browser_config.verbose == crawl_config.VERBOSE

    assert fetch_config.session_id == "topcv-run-1"
    assert fetch_config.page_timeout == 45000
    assert fetch_config.wait_for == "css:.custom-listing-ready"
    assert fetch_config.cache_mode == CacheMode.ENABLED

    assert detail_config.session_id == "topcv-run-1"
    assert detail_config.page_timeout == 45000
    assert detail_config.delay_before_return_html == 4.5
    assert detail_config.wait_for == "css:.custom-ready"
    assert detail_config.screenshot is False
    assert detail_config.cache_mode == CacheMode.ENABLED
    assert detail_config.magic is False
    assert detail_config.simulate_user is False
    assert detail_config.remove_overlay_elements is True
    assert detail_config.exclude_external_links is False
    assert detail_config.word_count_threshold == 9
    assert crawl_config.settings.crawler.max_retries == 7
    assert browser_config.proxy_config is None


def test_topcv_search_seeds_are_loaded_in_order():
    settings = Settings(
        crawler=CrawlerSettings(
            topcv=TopCVCrawlerSettings(
                search_seeds=[
                    TopCVCrawlerSettings.SearchSeed(
                        name="ai_engineer",
                        url="https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
                    ),
                    TopCVCrawlerSettings.SearchSeed(
                        name="data_scientist",
                        url="https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
                    ),
                ]
            )
        )
    )

    assert [seed.name for seed in settings.crawler.topcv.search_seeds] == ["ai_engineer", "data_scientist"]
    assert settings.search_urls == [
        "https://www.topcv.vn/tim-viec-lam-ai-engineer?sba=1",
        "https://www.topcv.vn/tim-viec-lam-data-scientist?sba=1",
    ]


def test_topcv_search_urls_fall_back_when_seeds_absent():
    settings = Settings(crawler=CrawlerSettings(topcv=TopCVCrawlerSettings(search_seeds=[])))

    assert settings.crawler.topcv.search_seeds == []
    assert settings.search_urls == []


def test_topcv_crawler_config_defaults_are_preserved():
    topcv = TopCVCrawlerSettings()

    assert topcv.headless is False
    assert topcv.enable_stealth is True
    assert topcv.user_agent_mode == "random"
    assert topcv.use_persistent_context is False
    assert topcv.user_data_dir is None
    assert topcv.storage_state_path is None
    assert topcv.page_timeout_ms == 60000
    assert topcv.delay_before_return_html == 5.0
    assert topcv.fetch_wait_for == "css:.job-item-search-result"
    assert topcv.wait_for == "css:h1, h2.title, .job-detail-title"
    assert topcv.screenshot is False
    assert topcv.cache_mode == "bypass"
    assert topcv.magic is True
    assert topcv.simulate_user is True
    assert topcv.remove_overlay_elements is False
    assert topcv.exclude_external_links is True
    assert topcv.word_count_threshold == 5
    assert topcv.detail_delay_min_seconds == 15.0
    assert topcv.detail_delay_max_seconds == 30.0
    assert topcv.blocked_delay_min_seconds == 30.0
    assert topcv.blocked_delay_max_seconds == 60.0
    assert topcv.blocked_early_stop_threshold == 1
    assert topcv.blocked_cooldown_minutes == 180
    assert topcv.proxy_enabled is False
    assert topcv.proxy_servers == [
        "dc.oxylabs.io:8001",
        "dc.oxylabs.io:8002",
        "dc.oxylabs.io:8003",
        "dc.oxylabs.io:8004",
        "dc.oxylabs.io:8005",
    ]
    assert topcv.proxy_rotation == "round_robin"
    assert topcv.proxy_username_env == "OXYLABS_USERNAME"
    assert topcv.proxy_password_env == "OXYLABS_PASSWORD"
    assert [seed.name for seed in topcv.search_seeds] == ["ai_engineer", "data_scientist"]


def test_crawler_settings_default_max_retries_is_still_available():
    settings = Settings()

    assert settings.crawler.max_retries == 2


def test_topcv_proxy_is_disabled_by_default():
    topcv = TopCVCrawlerSettings()

    assert topcv.proxy_enabled is False
    assert topcv.proxy_servers


def test_topcv_proxy_enabled_builds_proxy_config_and_uses_typed_env_credentials(monkeypatch):
    topcv = crawl_config.settings.crawler.topcv
    monkeypatch.setattr(topcv, "proxy_enabled", True)
    monkeypatch.setattr(topcv, "proxy_servers", ["dc.oxylabs.io:8001", "dc.oxylabs.io:8002"])
    monkeypatch.setattr(topcv, "proxy_rotation", "first")
    monkeypatch.setattr(topcv, "proxy_username_env", "OXYLABS_USERNAME")
    monkeypatch.setattr(topcv, "proxy_password_env", "OXYLABS_PASSWORD")
    monkeypatch.setenv("OXYLABS_USERNAME", "oxylabs-user")
    monkeypatch.setenv("OXYLABS_PASSWORD", "oxylabs-pass")

    browser_config = crawl_config.build_browser_config(session_id="run-proxy-1")
    fetch_config = crawl_config.build_fetch_link_run_config(session_id="run-proxy-1")
    detail_config = crawl_config.build_extract_detail_run_config(session_id="run-proxy-1")

    assert browser_config.proxy_config.server == "dc.oxylabs.io:8001"
    assert browser_config.proxy_config.username == "oxylabs-user"
    assert browser_config.proxy_config.password == "oxylabs-pass"
    assert fetch_config.proxy_config.server == "dc.oxylabs.io:8001"
    assert detail_config.proxy_config.server == "dc.oxylabs.io:8001"


def test_topcv_proxy_round_robin_rotation_uses_session_id(monkeypatch):
    topcv = crawl_config.settings.crawler.topcv
    monkeypatch.setattr(topcv, "proxy_enabled", True)
    monkeypatch.setattr(topcv, "proxy_servers", ["dc.oxylabs.io:8001", "dc.oxylabs.io:8002", "dc.oxylabs.io:8003"])
    monkeypatch.setattr(topcv, "proxy_rotation", "round_robin")
    monkeypatch.setattr(topcv, "proxy_username_env", "OXYLABS_USERNAME")
    monkeypatch.setattr(topcv, "proxy_password_env", "OXYLABS_PASSWORD")
    monkeypatch.setenv("OXYLABS_USERNAME", "user")
    monkeypatch.setenv("OXYLABS_PASSWORD", "pass")

    session_id = "topcv-run-rotation"
    expected_index = int(hashlib.sha256(session_id.encode("utf-8")).hexdigest(), 16) % 3
    expected_server = [
        "dc.oxylabs.io:8001",
        "dc.oxylabs.io:8002",
        "dc.oxylabs.io:8003",
    ][expected_index]

    proxy_config = crawl_config.build_browser_config(session_id=session_id).proxy_config

    assert proxy_config.server == expected_server


def test_topcv_proxy_enabled_without_credentials_fails_clearly(monkeypatch):
    topcv = crawl_config.settings.crawler.topcv
    monkeypatch.setattr(topcv, "proxy_enabled", True)
    monkeypatch.setattr(topcv, "proxy_servers", ["dc.oxylabs.io:8001"])
    monkeypatch.setattr(topcv, "proxy_rotation", "first")
    monkeypatch.setattr(topcv, "proxy_username_env", "MISSING_PROXY_USER")
    monkeypatch.setattr(topcv, "proxy_password_env", "MISSING_PROXY_PASS")
    monkeypatch.delenv("MISSING_PROXY_USER", raising=False)
    monkeypatch.delenv("MISSING_PROXY_PASS", raising=False)

    with pytest.raises(ValueError, match="credentials are missing"):
        crawl_config.build_browser_config(session_id="missing-creds")

