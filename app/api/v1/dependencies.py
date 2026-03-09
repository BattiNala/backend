"""Authentication and request-scoped dependencies for API v1."""

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.exceptions.auth_expection import CredentialException
from app.models.user import User
from app.repositories.user_repo import UserRepository

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Resolve and return the authenticated user from a bearer token."""
    credentials_exception = CredentialException()
    token = credentials.credentials

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except jwt.PyJWTError as exc:
        raise credentials_exception from exc
    user = await UserRepository(db).get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user


async def require_superadmin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ensure the current user has the superadmin role."""
    user_role_name = await UserRepository(db).get_user_role_name(current_user.user_id)
    if user_role_name != "superadmin":
        raise HTTPException(status_code=403, detail="Access forbidden: Superadmin only")
    return current_user


async def require_department_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ensure the current user has either the department admin or superadmin role."""
    user_role_name = await UserRepository(db).get_user_role_name(current_user.user_id)
    if user_role_name not in ["department_admin", "superadmin"]:
        raise HTTPException(
            status_code=403, detail="Access forbidden: Department Admin or Superadmin only"
        )
    return current_user


async def require_staff(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ensure the current user has either the staff or department admin."""
    user_role_name = await UserRepository(db).get_user_role_name(current_user.user_id)
    if user_role_name not in ["staff", "department_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Staff or Department Admin",
        )
    return current_user


async def require_citizen(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ensure the current user has either the citizen"""
    user_role_name = await UserRepository(db).get_user_role_name(current_user.user_id)
    if user_role_name != "citizen":
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Citizen only",
        )
    return current_user
