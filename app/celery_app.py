"""
Celery app configuration
"""

import logging

from celery import Celery
from celery.signals import setup_logging as celery_setup_logging

from app.core.logger import setup_logging

celery_app = Celery(
    "battinala",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
    include=["app.tasks.celery_jobs"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,
    worker_log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    task_log_format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@celery_setup_logging.connect
def on_celery_setup_logging(**kwargs):  # pylint: disable=unused-argument
    """Initialize app logging inside the Celery worker process.

    Without this, the app logger (battinala-backend) has no handlers in the
    worker process, so all calls to get_logger() inside tasks are silently
    discarded.
    """
    setup_logging()

    # Give the celery.task logger a stream handler so task-level log records
    # emitted by Celery itself are visible.
    task_logger = logging.getLogger("celery.task")
    if not task_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        task_logger.addHandler(handler)
