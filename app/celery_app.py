"""
Celery app configuration
"""

from celery import Celery

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
)
