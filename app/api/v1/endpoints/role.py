"""Role endpoints for administrative operations. Superadmin-only access is required for role management."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import router
from app.db.session import get_db
from app.models.user import User

from app.api.v1.dependencies import get_current_user
from app.repositories.user_repo import UserRepository
from app.repositories.role_repo import RoleRepository
from app.schemas.roles import RoleCreate, RoleList
router = APIRouter()
    
@router.post("/create-role")
async def create_role(
    role_create: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new role when requested by a superadmin user."""
    try:
        user_repo = UserRepository(db)
        user_role_name = await user_repo.get_user_role_name(current_user.user_id)
        if user_role_name != "superadmin":
            raise HTTPException(
                status_code=403, detail="Access forbidden: Superadmin only"
            )

        existing_role = await RoleRepository(db).get_role_by_name(role_create.role_name)
        if existing_role:
            raise HTTPException(status_code=400, detail="Role already exists")

        new_role = await RoleRepository(db).create_role(role_create.role_name)
        return {"message": f"Role '{new_role.role_name}' created successfully"}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/list-roles", response_model=RoleList)
async def list_roles(
    db: AsyncSession = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """List all roles."""
    try:
        roles = await RoleRepository(db).list_roles()
        return {"roles": roles}

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc