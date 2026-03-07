"""Main API v1 router registration."""

from fastapi import APIRouter
from app.api.v1.endpoints import department, issues, routes, auth, superadmin, role,department

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(role.router, prefix="/role", tags=["role"])
api_router.include_router(department.router, prefix="/department", tags=["department"])
api_router.include_router(issues.router, prefix="/issues", tags=["issues"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
api_router.include_router(superadmin.router, prefix="/superadmin", tags=["superadmin"])
