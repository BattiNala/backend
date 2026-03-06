"""Issue endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_issues():
    """Return a placeholder issue list response."""
    return {"items": []}


@router.post("/")
def create_issue():
    """Return a placeholder issue creation response."""
    return {"created": True}
