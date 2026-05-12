# Battinala Backend

A civic infrastructure issue management platform - citizens report problems (potholes, fallen trees, sewage leaks, etc.), government departments triage and resolve them, powered by AI-driven verification and custom geospatial routing.

**Version:** 0.2.0 | **Python:** 3.12 | **Framework:** FastAPI (async)

---

## Features

- **Issue Management** — Report, verify, assign, resolve, and track infrastructure issues with full lifecycle management
- **AI/ML Verification** — Multi-LLM (Gemini, Mistral, Groq) image validation + computer vision duplicate detection (pHash, ORB, histogram, embeddings)
- **Custom Routing Engine** — Bidirectional A* search on OpenStreetMap data with Haversine heuristic, nearest-node snapping, and Douglas-Peucker path simplification
- **Automated Assignment** — Celery background jobs assign verified issues to the nearest available employee
- **RBAC** — Four roles: `superadmin`, `department_admin`, `staff`, `citizen` with hierarchical access control
- **Analytics** — Department/employee/team performance metrics, issue trends, and dashboard summaries
- **Async Everything** — Async SQLAlchemy + asyncpg, aioboto3 for S3, aiosmtplib for email
- **Dockerized** — Production and development Docker Compose stacks with hot-reload

---

## Tech Stack

| Category | Technology |
|----------|-----------|
| **Language** | Python 3.12 |
| **Web Framework** | FastAPI (async) |
| **Database** | PostgreSQL 16 + pgvector |
| **ORM** | SQLAlchemy 2.0 (async) / Alembic |
| **Task Queue** | Celery + Redis 7 |
| **Storage** | S3-compatible (AWS S3, MinIO, Cloudflare R2) via aioboto3 |
| **AI/ML** | Google Gemini, Mistral AI, Groq, OpenCV, imagehash |
| **Geospatial** | Custom A* routing on OSM PBF data (osmium) |
| **Auth** | JWT (python-jose), Argon2 password hashing |
| **Email** | SMTP via aiosmtplib (Mailpit in dev) |
| **CI/CD** | GitHub Actions (pylint + pytest per push/PR) |
| **Package Manager** | `uv` (Astral) |

---

## Project Structure

```
app/                    # Main application package
├── api/v1/
│   ├── endpoints/      # All API route handlers
│   ├── dependencies.py # Auth/RBAC dependencies
│   ├── rbac.py         # Role-based access control
│   └── router.py       # Route wiring
├── core/               # Config, constants, logging
├── db/                 # SQLAlchemy engine + session
├── exceptions/         # Custom exception classes
├── models/             # 15 ORM models (User, Issue, Employee, etc.)
├── repositories/       # Data access layer (11 repos)
├── schemas/            # Pydantic request/response schemas
├── services/           # Business logic (9 services)
├── tasks/              # Celery background jobs (6 modules)
├── routing/            # Custom OSM routing engine (9 modules)
├── utils/              # Shared utilities (13 modules)
├── seeders/            # DB seeders
├── main.py             # FastAPI app entrypoint
├── celery_app.py       # Celery configuration
alembic/                # 32 database migration scripts
tests/                  # Unit tests (CI) + CLI integration tests
dev_scripts/            # Helper scripts
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- `uv` package manager (`pip install uv`)

### Setup

```bash
# Clone and enter the repo
git clone https://github.com/battinala/backend
cd backend

# Copy environment config
cp .env.example .env
# Edit .env with your keys (DB, S3, JWT, LLM API keys, etc.)

# Start the dev stack
./start.sh
```

This starts: API server (hot-reload on :8000), PostgreSQL 16 + pgvector, Redis 7, Celery worker, and Mailpit (email UI on :8025).

### Manual Commands

```bash
uv sync --locked --all-extras --dev       # Install all dependencies
uv run alembic upgrade head               # Apply migrations
uv run uvicorn app.main:app --reload       # Dev server
uv run celery -A app.celery_app worker     # Celery worker
uv run pytest tests/unit_tests             # Run unit tests
uv run ruff check .                        # Lint (Ruff)
uv run pylint -j 0 app                     # Lint (Pylint)
```

---

## API Overview

All endpoints are under `/api/v1/`. Key groups:

| Group | Key Endpoints |
|-------|--------------|
| **Auth** | Register, login, refresh, OTP verification, password reset |
| **Issues** | Create (anon/authenticated), list, verify, update status, resolve, reject |
| **Teams** | Create, list, get by ID (department_admin) |
| **Employees** | Add staff, change team |
| **Routes** | `POST /shortest` — A* shortest path between two coordinates |
| **Analytics** | Issue stats, trends, top employees/teams, dashboard |
| **Admin** | Role/Department CRUD (superadmin) |

---

## Background Jobs (Celery)

| Task | Trigger | What it does |
|------|---------|-------------|
| `process_new_issue_task` | New issue created | Validates images via LLM, detects duplicates (pHash/ORB/histogram/embeddings), auto-rejects or flags for review |
| `generate_issue_embeddings_task` | New attachment | Generates Gemini image embeddings stored in pgvector |
| `assign_issue_to_nearest_employee_task` | Issue verified | Geo-assigns to nearest available employee |

---

## Environment Variables

Key variables (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | PostgreSQL connection |
| `JWT_SECRET` | JWT signing secret |
| `S3_*` | S3-compatible storage config |
| `SMTP_*` | Email server config |
| `GEMINI_API_KEY` | Google Gemini (embeddings + vision) |
| `MISTRAL_API_KEY` | Mistral AI (LLM verification) |
| `GROQ_API_KEY` | Groq (alternative LLM) |
| `REDIS_HOST` / `REDIS_PORT` | Redis connection |

---

## Documentation
- **`ALGOS.md`** — Routing algorithm details (A*, Haversine, path simplification)
- **`CONTRIBUTING.md`** — How to contribute

---

## License

See the [LICENSE](LICENSE) file.
