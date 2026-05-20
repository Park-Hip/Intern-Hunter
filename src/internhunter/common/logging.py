from __future__ import annotations

import logging
import sys
from typing import List

import structlog
from structlog.types import Processor

from src.internhunter.config.settings import settings


def _ensure_utf8_text_stream(stream) -> None:
    """Make text streams safe for Windows consoles and mixed Unicode log output."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # If the stream refuses reconfiguration, fall back to the existing encoding.
            pass


def get_processors(log_format: str) -> List[Processor]:
    common_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_format == "json":
        return common_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]

    return common_processors + [
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        ),
    ]


def configure_logging() -> None:
    log_format = settings.logging.format.lower()
    log_level = settings.logging.level.upper()

    # Ensure the process can safely print Crawl4AI progress symbols and other Unicode
    # log text on Windows consoles without raising UnicodeEncodeError.
    _ensure_utf8_text_stream(sys.stdout)
    _ensure_utf8_text_stream(sys.stderr)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level, logging.INFO),
    )

    structlog.configure(
        processors=get_processors(log_format),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog.stdlib.logging, log_level, structlog.stdlib.logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_context(**kwargs) -> None:
    structlog.contextvars.bind_contextvars(**kwargs)


def reset_context(**kwargs) -> None:
    structlog.contextvars.clear_contextvars()
    if kwargs:
        structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()


__all__ = [
    "bind_context",
    "clear_context",
    "configure_logging",
    "get_logger",
    "get_processors",
    "reset_context",
]
