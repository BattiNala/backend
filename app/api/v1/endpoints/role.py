"""
Role endpoints for administrative operations.
Superadmin-only access is required for role management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user, require_superadmin
from app.api.v1.utils import with_db_error
from app.db.session import get_db
from app.repositories.role_repo import RoleRepository
from app.schemas.roles import RoleCreate, RoleList

role_router = APIRouter()


@role_router.post("/create-role", dependencies=[Depends(require_superadmin)])
async def create_role(
    role_create: RoleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new role when requested by a superadmin user."""
    async def _create() -> dict:
        existing_role = await RoleRepository(db).get_role_by_name(role_create.role_name)
        if existing_role:
            raise HTTPException(status_code=400, detail="Role already exists")

        new_role = await RoleRepository(db).create_role(role_create.role_name)
        return {"message": f"Role '{new_role.role_name}' created successfully"}

    return await with_db_error(_create)


@role_router.get(
    "/list-roles",
    response_model=RoleList,
    dependencies=[Depends(get_current_user)],
)
async def list_roles(
    db: AsyncSession = Depends(get_db),
):
    """List all roles."""
    async def _list() -> dict:
        roles = await RoleRepository(db).list_roles()
        return {"roles": roles}

    return await with_db_error(_list)
