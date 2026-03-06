"""Application entrypoint and router wiring."""

from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(title=settings.APP_NAME, version=settings.VERSION)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
def health():
    """Return service liveness status."""
    return {"status": "ok"}
