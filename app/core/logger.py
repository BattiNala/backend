"""Centralized logging configuration for the application."""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path

APP_LOGGER_NAME = "battinala-backend"
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIR / f"app_{datetime.now().strftime('%Y-%m-%d')}.log"


LEVEL_NAMES = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


def _resolve_level(level: int | str | None) -> int:
    """Resolve a numeric logging level from int/string/env input."""
    if isinstance(level, int):
        return level

    candidate = level or os.getenv("LOG_LEVEL", "INFO")
    if isinstance(candidate, str):
        return LEVEL_NAMES.get(candidate.strip().upper(), logging.INFO)

    return logging.INFO


def setup_logging(level: int | str | None = None) -> logging.Logger:
    """Configure and return the application logger.

    Repeated calls are safe: existing handlers created by this setup are replaced.
    """
    resolved_level = _resolve_level(level)
    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(resolved_level)
    logger.propagate = False

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Replace handlers to keep setup idempotent across test runs/reloads.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    console_handler = logging.StreamHandler()
    console_handler.setLevel(resolved_level)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # file_handler = logging.handlers.RotatingFileHandler(
    #     LOG_FILE,
    #     maxBytes=10 * 1024 * 1024,
    #     backupCount=5,
    #     encoding="utf-8",
    # )
    file_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE,
        when="midnight",  # rotate at midnight
        interval=1,  # every 1 day
        backupCount=7,  # keep 7 days
        encoding="utf-8",
        utc=False,
    )

    file_handler.setLevel(resolved_level)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return an application child logger after ensuring base config exists."""
    if not logging.getLogger(APP_LOGGER_NAME).handlers:
        setup_logging()

    if not name:
        return logging.getLogger(APP_LOGGER_NAME)

    return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")


app_logger = setup_logging()
