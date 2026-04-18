# Contributing to Battinala Backend

This project is a FastAPI backend with PostgreSQL, Alembic migrations, Redis, and Celery workers. Use this guide to set up a local environment, run the checks that matter, and open changes that match the repo's current workflow.

## Prerequisites

- Python `3.12`
- `uv`
- Docker with Docker Compose

## Project Layout

- `app/`: application code
- `tests/unit_tests/`: unit tests covered by CI
- `tests/cli_tests/`: manual or environment-dependent scripts and checks
- `alembic/`: database migrations
- `dev_scripts/`: helper scripts for development tasks

## Local Setup

1. Install dependencies:

```bash
uv sync --locked --all-extras --dev
```

2. Create a local `.env` file.

The file is ignored by Git and is required for local app runs. At minimum, set the database, JWT, and S3-related variables used by `app/core/config.py`.

Commonly needed variables:

- `DB_HOST`
- `DB_PORT`
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `JWT_SECRET`
- `S3_ENDPOINT_URL`
- `S3_ACCESS_KEY_ID`
- `S3_SECRET_ACCESS_KEY`

If you are working on mail, LLM, embedding, or storage features, also set the related SMTP, Gemini, Groq, or other service variables needed by that code path.

3. Start the local stack:

```bash
./start.sh
```

That starts:

- API on `http://localhost:8000`
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- Mailpit UI on `http://localhost:8025`
- Celery worker

If your Docker setup does not require `sudo`, you can run Compose directly instead of using the helper script.

4. Stop the local stack when finished:

```bash
./stop.sh
```

Health check:

```bash
curl http://localhost:8000/health
```

Note: app startup warms the route graph from `kathmandu_valley.osm.pbf`, so first boot can take longer than a minimal FastAPI service.

## Running the App Without Docker

If you already have PostgreSQL and Redis available locally, you can run the API directly:

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

You may also need a separate Celery worker for task-related changes:

```bash
uv run celery -A app.celery_app worker --loglevel=info
```

## Quality Checks

Run these before opening a PR:

```bash
uv run ruff check .
uv run ruff format .
uv run pylint -j 0 app tests
uv run pytest tests/unit_tests
```

Notes:

- CI currently runs `pylint` on `app/` and `pytest` on `tests/unit_tests`.
- `tests/cli_tests/` are not part of CI and often require extra services or manual setup.
- The repo also includes a pre-commit configuration for Ruff, whitespace checks, YAML validation, and pylint.

Optional but recommended:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

## Database Changes

If your change modifies SQLAlchemy models or database structure:

1. Generate a migration:

```bash
./dev_scripts/make_migrations.sh
```

2. Review the generated Alembic file carefully.
3. Apply migrations locally:

```bash
uv run alembic upgrade head
```

Do not merge model changes without the corresponding Alembic revision.

## Tests

- Add or update unit tests for behavior changes.
- Keep tests close to the code they validate when possible.
- Prefer targeted tests over large end-to-end additions unless the feature actually crosses multiple layers.

Useful commands:

```bash
uv run pytest tests/unit_tests/services
uv run pytest tests/unit_tests/api
uv run pytest tests/unit_tests/routing
```

## Pull Requests

Keep PRs focused and easy to review.

Before opening a PR:

- Rebase or merge from the latest target branch as needed.
- Run the quality checks listed above.
- Include migrations with schema changes.
- Update tests for behavior changes.
- Mention any required env vars, manual verification, or follow-up work in the PR description.

The repository has a PR label check. Add, or ask a maintainer to add, at least one valid type label:

- `enhancement`
- `bug`
- `bugfix`
- `chore`
- `documentation`
- `dependencies`
- `depandabot`
- `python:uv`

## What Not to Commit

- Secrets or `.env` files
- Local caches, logs, or virtual environments
- Temporary manual-use artifacts
- Large generated files unless the change explicitly requires them

In particular, treat files like `openapi.json` and the Postman collection generator as local temporary tooling unless a maintainer explicitly asks for them to be part of your change.
