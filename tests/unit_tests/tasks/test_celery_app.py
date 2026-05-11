# pylint: disable=missing-module-docstring, missing-function-docstring, redefined-outer-name
import logging
from types import SimpleNamespace

from app.celery_app import celery_app
from app.core.logger import setup_logging
from app.tasks import celery_jobs


def test_celery_logging_configuration_is_complete():
    """Test that Celery app has proper logging configuration to prevent swallowing app logs."""
    # Check that worker doesn't hijack root logger (which would disable our app logger)
    assert celery_app.conf.worker_hijack_root_logger is False

    # Check that log formats are set
    assert (
        celery_app.conf.worker_log_format == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    assert celery_app.conf.task_log_format == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def test_celery_app_logger_initialization():
    """Test that the Celery app properly initializes logging."""
    # Test that our configuration prevents logger conflicts
    # Setup logging - should not raise exceptions
    logger = setup_logging()
    assert logger is not None
    assert logger.name == "battinala-backend"

    # Test that we can get child loggers
    child_logger = logging.getLogger("battinala-backend.test")
    assert child_logger is not None


def test_celery_imports_register_issue_assignment_task():
    celery_app.loader.import_default_modules()

    assert "app.tasks.assign_issue_to_nearest_employee" in celery_app.tasks


def test_celery_imports_register_issue_processing_task():
    celery_app.loader.import_default_modules()

    assert "app.tasks.process_new_issue" in celery_app.tasks


def test_celery_imports_register_issue_embedding_task():
    celery_app.loader.import_default_modules()

    assert "app.tasks.generate_issue_embeddings" in celery_app.tasks


def test_run_async_reuses_runner(monkeypatch):
    calls = []

    def _run(coro):
        calls.append(coro)
        coro.close()
        return "ok"

    fake_runner = SimpleNamespace(run=_run)
    monkeypatch.setattr(celery_jobs, "get_runner", lambda: fake_runner)

    async def _sample():
        return "done"

    assert celery_jobs.run_async(_sample()) == "ok"
    assert celery_jobs.run_async(_sample()) == "ok"
    assert calls
    assert len(calls) == 2


def test_celery_app_worker_hijack_root_logger_is_false():
    """Ensure Celery app does not hijack the root logger."""
    assert celery_app.conf.worker_hijack_root_logger is False


def test_celery_app_log_formats_are_set():
    """Ensure worker and task log formats are configured."""
    assert (
        celery_app.conf.worker_log_format == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    assert celery_app.conf.task_log_format == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def test_celery_task_logger_emits_logs(caplog):
    """Test that a Celery task actually emits logs when run eagerly."""
    # Initialize logging for the test context
    setup_logging()

    # Ensure tasks are imported
    celery_app.loader.import_default_modules()

    # Create a simple test task
    @celery_app.task(name="test.logging.task")
    def test_logging_task():
        from app.core.logger import get_logger  # pylint: disable=import-outside-toplevel

        logger = get_logger("test")
        logger.info("Test log message from Celery task")
        return "done"

    # Run the task eagerly (without worker) and capture logs
    with caplog.at_level(logging.INFO):
        result = test_logging_task.apply(args=(), kwargs={}).get()

    assert result == "done"
    # Check that our log message was captured
    assert any("Test log message from Celery task" in record.message for record in caplog.records)
    # Also check that it came from the right logger
    assert any(record.name == "battinala-backend.test" for record in caplog.records)
