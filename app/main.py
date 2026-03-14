"""Application entrypoint and router wiring."""

from contextlib import asynccontextmanager
from datetime import datetime
from time import perf_counter as _perf_counter

from fastapi import FastAPI

from app.api.v1.endpoints.routes import _route_service
from app.api.v1.router import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Warm the route graph on startup to improve first-request latency."""
    started_at = _perf_counter()
    print(
        f"[{datetime.now().isoformat(timespec='milliseconds')}] app_startup "
        "warming_route_graph: begin"
    )
    _route_service.ensure_loaded()
    elapsed_ms = (_perf_counter() - started_at) * 1000.0
    print(
        f"[{datetime.now().isoformat(timespec='milliseconds')}] app_startup "
        f"warming_route_graph: done in {elapsed_ms:.2f} ms"
    )
    yield


app = FastAPI(title=settings.APP_NAME, version=settings.VERSION, lifespan=lifespan)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
def health():
    """Return service liveness status."""
    return {"status": "ok"}
