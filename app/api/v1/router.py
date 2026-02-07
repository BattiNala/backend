from fastapi import APIRouter
from app.api.v1.endpoints import issues, routes

api_router = APIRouter()

api_router.include_router(issues.router, prefix="/issues", tags=["issues"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
