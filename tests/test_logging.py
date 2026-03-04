import logging
import logging.handlers

from app.core import logging as log_module


def test_logging_setup_creates_handlers_and_dir():
    logger = log_module.logger

    assert logger.name == "battinala-backend"
    assert log_module.LOG_DIR.exists()

    handler_types = {type(handler) for handler in logger.handlers}
    assert logging.StreamHandler in handler_types
    assert logging.handlers.RotatingFileHandler in handler_types
