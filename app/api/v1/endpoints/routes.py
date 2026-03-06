"""Route planning endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.post("/generate")
def generate_route():
    """Return a placeholder generated route payload."""
    return {"route": []}
