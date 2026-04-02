# pylint: disable=missing-module-docstring, missing-function-docstring
from app.celery_app import celery_app


def test_celery_imports_register_issue_assignment_task():
    celery_app.loader.import_default_modules()

    assert "app.tasks.assign_issue_to_nearest_employee" in celery_app.tasks
