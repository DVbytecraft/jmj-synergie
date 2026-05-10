"""
Structured logging setup — structlog + stdlib integration.
"""
import logging
import sys

import structlog
from app.core.config import settings


def configure_logging() -> None:
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.stdlib.add_logger_name,
    ]

    if settings.is_production:
        # JSON in production (ingested by log aggregator)
        renderer = structlog.processors.JSONRenderer()
    else:
        # Pretty colors in development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.DEBUG else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Silence noisy third-party loggers
    for noisy in ("sqlalchemy.engine", "passlib", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    return structlog.get_logger(name)
