import hashlib
import os

from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode, ProxyConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

from src.internhunter.common.logging import get_logger
from src.internhunter.config.settings import settings

# Production: quiet by default. Override verbosity locally with CRAWL_VERBOSE=1.

logger = get_logger(__name__)
VERBOSE = os.getenv("CRAWL_VERBOSE", "false").lower() in ("1", "true", "yes")
HEADLESS = settings.crawler.topcv.headless

# Run schema for fetching links process
fetch_link_schema = {
        "name": "Job Links",
        "baseSelector": ".job-item-search-result",
        "fields": [
            {
                "name": "url",
                "selector": "h3.title a",
                "type": "attribute",
                "attribute": "href"
            }
        ]
    }

def build_fetch_link_run_config(session_id: str | None = None) -> CrawlerRunConfig:
    """Build the Crawl4AI config used to fetch paginated TopCV listing pages."""
    topcv = settings.crawler.topcv
    proxy_config = _build_topcv_proxy_config(session_id=session_id)
    return CrawlerRunConfig(
        extraction_strategy=JsonCssExtractionStrategy(fetch_link_schema),
        cache_mode=_resolve_cache_mode(topcv.cache_mode),
        wait_for=topcv.fetch_wait_for,
        page_timeout=topcv.page_timeout_ms,
        proxy_config=proxy_config,
        session_id=session_id,
    )

# Run schema for extracting single job details
extract_detail_schema = {
    "name": "TopCV Extraction",
    "baseSelector": "html",
    "fields": [
        {
            "name": "title",
            "selector": ", ".join([
                ".text-premium",
                # "h1",
                ".job-detail__info--title",
                ".job-detail-title",
                ".title-job",
                ".premium-job-basic-information__content--title a",
                "h2.title",
                "h2.title:has(.icon-verified-employer)", 
                "#header-job-info h2"
            ]),
            "type": "text"
        },
        {
            "name": "company",
            "selector": ", ".join([
                ".company-name-label a",
                ".company-content__title--name",
                ".box-info-job .company-title",
                "a.company-name",
                ".sidebar-brand-name",
                ".box-company-name",
                ".company-name",
                ".breadcrumb li:nth-last-child(2) a",
                ".footer-info-company-name"
            ]),
            "type": "text"
        },
        {
            "name": "salary",
            "selector": ", ".join([
                ".section-salary .job-detail__info--section-content-value",
                ".box-item:has(.fa-money-bill-wave) span",
                ".box-item:has(.fa-sack-dollar) span"
            ]),
            "type": "text"
        },
        {
            "name": "location",
            "selector": ", ".join([
                ".section-location .job-detail__info--section-content-value",
                ".box-item:has(.fa-location-dot) span",
                ".box-item:has(.fa-map-marker-alt) span",
                ".box-address"
            ]),
            "type": "text"
        },
        {
            "name": "experience",
            "selector": ", ".join([
                "#job-detail-info-experience .job-detail__info--section-content-value",
                ".box-item:has(.fa-star) span"
            ]),
            "type": "text"
        },
        {
            "name": "info",
            "selector": ", ".join([
                ".job-description",
                ".premium-job-description__box--content",
                ".content-tab",
                "#box-job-information"
            ]),
            "type": "text"
        },
    ]
}


extraction_strategy = JsonCssExtractionStrategy(extract_detail_schema)
# css_selector_filter = "#header-job-info, .box-main, .job-detail__box--right, .job-description, .box-info-job"


def build_extract_detail_run_config(session_id: str | None = None) -> CrawlerRunConfig:
    """Build the Crawl4AI config used to extract individual TopCV job pages."""
    topcv = settings.crawler.topcv
    proxy_config = _build_topcv_proxy_config(session_id=session_id)
    return CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        cache_mode=_resolve_cache_mode(topcv.cache_mode),
        magic=topcv.magic,
        simulate_user=topcv.simulate_user,
        page_timeout=topcv.page_timeout_ms,
        delay_before_return_html=topcv.delay_before_return_html,
        wait_for=topcv.wait_for,
        word_count_threshold=topcv.word_count_threshold,
        remove_overlay_elements=topcv.remove_overlay_elements,
        exclude_external_links=topcv.exclude_external_links,
        screenshot=topcv.screenshot,
        proxy_config=proxy_config,
        session_id=session_id,
    )


def _resolve_cache_mode(mode_name: str | None) -> CacheMode:
    """Map a human-readable cache mode name to Crawl4AI's CacheMode enum."""
    normalized = (mode_name or "bypass").strip().lower().replace("-", "_")
    mapping = {
        "enabled": CacheMode.ENABLED,
        "disabled": CacheMode.DISABLED,
        "read_only": CacheMode.READ_ONLY,
        "write_only": CacheMode.WRITE_ONLY,
        "bypass": CacheMode.BYPASS,
    }
    return mapping.get(normalized, CacheMode.BYPASS)


def _normalize_proxy_server(server: str) -> str:
    """Normalize a proxy server string to the host:port form Crawl4AI expects."""
    cleaned = (server or "").strip()
    if not cleaned:
        return cleaned
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[1]
    return cleaned


def _select_proxy_server(topcv, session_id: str | None = None) -> str:
    """Select one configured TopCV proxy server using the requested rotation mode."""
    servers = [server.strip() for server in topcv.proxy_servers if server and server.strip()]
    if not servers:
        raise ValueError("TopCV proxy is enabled but proxy_servers is empty.")

    rotation = (topcv.proxy_rotation or "first").strip().lower()
    if rotation == "round_robin" and session_id:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
        index = int(digest, 16) % len(servers)
    else:
        index = 0

    return _normalize_proxy_server(servers[index])


def _build_topcv_proxy_config(session_id: str | None = None) -> ProxyConfig | None:
    """Build a Crawl4AI proxy config for TopCV when proxy support is enabled."""
    topcv = settings.crawler.topcv
    if not topcv.proxy_enabled:
        return None

    proxy_username = os.getenv(topcv.proxy_username_env or "")
    proxy_password = os.getenv(topcv.proxy_password_env or "")
    if not proxy_username or not proxy_password:
        raise ValueError(
            "TopCV proxy is enabled but credentials are missing. "
            f"Expected environment variables: {topcv.proxy_username_env}, {topcv.proxy_password_env}."
        )

    server = _select_proxy_server(topcv, session_id=session_id)
    logger.info(
        "TopCV proxy enabled",
        proxy_server=server,
        proxy_rotation=topcv.proxy_rotation,
        session_id=session_id,
    )
    return ProxyConfig(server=server, username=proxy_username, password=proxy_password)


def build_browser_config(session_id: str | None = None) -> BrowserConfig:
    """Build the Crawl4AI browser config for TopCV crawling."""
    topcv = settings.crawler.topcv
    proxy_config = _build_topcv_proxy_config(session_id=session_id)
    return BrowserConfig(
        headless=topcv.headless,
        enable_stealth=topcv.enable_stealth,
        verbose=VERBOSE,
        user_agent_mode=topcv.user_agent_mode,
        use_persistent_context=topcv.use_persistent_context,
        user_data_dir=topcv.user_data_dir,
        storage_state=topcv.storage_state_path,
        proxy_config=proxy_config,
    )


fetch_link_run_config = build_fetch_link_run_config()
extract_detail_run_config = build_extract_detail_run_config()

# Browser config (headless + anti-bot experiment knobs from settings.yaml)
browser_config = build_browser_config()


