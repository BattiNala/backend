"""Tests for logger."""

# pylint: disable=protected-access

import logging

from app.core import logger as log_module


def test_resolve_level_handles_numeric_string_and_invalid_values(monkeypatch):
    """Test resolve level handles numeric string and invalid values."""
    monkeypatch.setenv("LOG_LEVEL", "debug")

    assert log_module._resolve_level(None) == logging.DEBUG
    assert log_module._resolve_level("warning") == logging.WARNING
    assert log_module._resolve_level(logging.ERROR) == logging.ERROR
    assert log_module._resolve_level("not-a-level") == logging.INFO


def test_setup_logging_is_idempotent_and_writes_to_temp_dir(monkeypatch, tmp_path):
    """Test setup logging is idempotent and writes to temp dir."""
    monkeypatch.setattr(log_module, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(log_module, "LOG_FILE", tmp_path / "logs" / "app.log")

    logger = log_module.setup_logging("INFO")
    same_logger = log_module.setup_logging("DEBUG")

    assert logger is same_logger
    assert logger.level == logging.DEBUG
    assert log_module.LOG_DIR.exists()
    assert len(logger.handlers) == 2


def test_get_logger_returns_child_logger():
    """Test get logger returns child logger."""
    logger = log_module.get_logger("routing")

    assert logger.name == "battinala-backend.routing"
