"""
Minimal structlog-based logging setup.

Exposes a small surface - `get_logger`, `LogConfig`, `initialize_multiple_loggers` - so the rest
of the app configures logging in one place and never touches structlog directly.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import structlog


@dataclass
class LogConfig:
    """Configuration for a single logger."""

    log_name: str
    log_format: str
    log_handler: str
    log_level: str


def initialize_multiple_loggers(configs: list[LogConfig]) -> None:
    """Configure structlog + stdlib logging from a list of `LogConfig`s (root logger only, in practice)."""
    for config in configs:
        level = getattr(logging, config.log_level.upper(), logging.INFO)
        stream = sys.stdout if config.log_handler == "stdout" else sys.stderr
        logging.basicConfig(level=level, stream=stream, format="%(message)s", force=True)

        renderer = (
            structlog.dev.ConsoleRenderer()
            if config.log_format == "console-simple"
            else structlog.processors.JSONRenderer()
        )
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(level),
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to `name`."""
    return structlog.get_logger(name)
