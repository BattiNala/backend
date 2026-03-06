"""Main API v1 router registration."""

from fastapi import APIRouter
from app.api.v1.endpoints import issues, routes, auth, superadmin

api_router = APIRouter()

api_router.include_router(issues.router, prefix="/issues", tags=["issues"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(superadmin.router, prefix="/superadmin", tags=["superadmin"])
