"""
Module for Service Configuration and Initialization.

This module is responsible for:
    - Loading the configuration from a specified YAML file
    - Initializing logging settings using logging_setup

Logging is set up using the logging_setup library which is configured to output logs to the console.
"""

import logging
from functools import lru_cache
from pathlib import Path

import logging_setup
from dynaconf import Dynaconf


logger = logging_setup.get_logger(__name__)


basepath = Path(__file__).parent
config_path = basepath / "settings.yml"


settings = Dynaconf(
    root_path=basepath,
    settings_files=[config_path],
    envvar_prefix="ECLIPSE_TRACKER",
    env_switcher="ECLIPSE_TRACKER_ENV",
    environments=True,
)

logger.info(
    "configuration_loaded_successfully",
    env=settings.current_env,
    filename=str(basepath),
)


@lru_cache
def initialize_logging() -> None:
    """
    Initialize logging_setup settings for logging throughout the application.
    This function is cached to ensure that logging settings are only initialized once.
    """
    logger.info("logging_initializing")

    root_config = logging_setup.LogConfig(
        log_name="",
        log_format=settings.logging.log_format,
        log_handler=settings.logging.log_handler,
        log_level=settings.logging.log_level,
    )
    logging_setup.initialize_multiple_loggers([root_config])
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("multipart").setLevel(logging.INFO)
    logging.getLogger("uvicorn").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging_setup.get_logger(__name__).info("logging_initialized")
