"""Superadmin-only endpoints for administrative operations."""

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import require_superadmin

superadmin_router = APIRouter()


@superadmin_router.get("/superadmin-only", dependencies=[Depends(require_superadmin)])
async def superadmin_only():
    """Allow access only to users with the superadmin role."""
    return {"message": "Welcome, Superadmin!"}
