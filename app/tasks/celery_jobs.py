"""Celery task wrappers for async job entrypoints."""

from functools import lru_cache

from app.celery_app import celery_app
from app.tasks.jobs import process_issue
from app.tasks.task_assign_job import assign_issue_to_nearest_employee


@lru_cache(maxsize=1)
def get_runner():
    """Create one asyncio.Runner per worker process."""
    import asyncio  # pylint: disable=import-outside-toplevel

    return asyncio.Runner()


def run_async(coro):
    """Run a coroutine on a persistent event loop per worker process."""
    return get_runner().run(coro)


@celery_app.task(
    name="app.tasks.assign_issue_to_nearest_employee",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def assign_issue_to_nearest_employee_task(issue_id: int) -> None:
    """Celery task wrapper for assign_issue_to_nearest_employee."""
    run_async(assign_issue_to_nearest_employee(issue_id))


@celery_app.task(
    name="app.tasks.process_new_issue",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def process_new_issue_task(issue_id: int):
    """Celery task wrapper for processing a new issue."""
    run_async(process_issue(issue_id))
