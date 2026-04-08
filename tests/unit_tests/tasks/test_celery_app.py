# pylint: disable=missing-module-docstring, missing-function-docstring
from types import SimpleNamespace

from app.celery_app import celery_app
from app.tasks import celery_jobs


def test_celery_imports_register_issue_assignment_task():
    celery_app.loader.import_default_modules()

    assert "app.tasks.assign_issue_to_nearest_employee" in celery_app.tasks


def test_celery_imports_register_issue_processing_task():
    celery_app.loader.import_default_modules()

    assert "app.tasks.process_new_issue" in celery_app.tasks


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
