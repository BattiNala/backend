"""Main API v1 router registration."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, department, issues, profile, role, routes, superadmin, team

api_router = APIRouter()

api_router.include_router(auth.auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(profile.profile_router, prefix="/profile", tags=["profile"])
api_router.include_router(role.role_router, prefix="/role", tags=["role"])
api_router.include_router(department.department_router, prefix="/department", tags=["department"])
api_router.include_router(issues.issue_router, prefix="/issues", tags=["issues"])
api_router.include_router(team.team_router, prefix="/team", tags=["team"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
api_router.include_router(superadmin.superadmin_router, prefix="/superadmin", tags=["superadmin"])
