"""Superadmin-only endpoints for administrative operations."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User

from app.api.v1.dependencies import get_current_user
from app.repositories.user_repo import UserRepository
from app.repositories.role_repo import RoleRepository
from app.schemas.roles import RoleCreate

router = APIRouter()


@router.get("/superadmin-only")
async def superadmin_only(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allow access only to users with the superadmin role."""

    user_repo = UserRepository(db)
    user_role_name = await user_repo.get_user_role_name(current_user.user_id)
    if user_role_name != "superadmin":
        raise HTTPException(status_code=403, detail="Access forbidden: Superadmin only")
    return {"message": "Welcome, Superadmin!"}
