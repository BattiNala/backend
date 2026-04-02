"""
Celery Jobs Wrapper
"""

import asyncio

from app.celery_app import celery_app
from app.tasks.jobs import assign_issue_to_nearest_employee


@celery_app.task(
    name="app.tasks.assign_issue_to_nearest_employee",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def assign_issue_to_nearest_employee_task(issue_id: int) -> None:
    """Celery task wrapper for assign_issue_to_nearest_employee."""
    asyncio.run(assign_issue_to_nearest_employee(issue_id))
