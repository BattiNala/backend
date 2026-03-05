from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.models.citizens import Citizen
from app.models.roles import Role

from app.schemas.auth import (
    UserLogin,
    TokenResponse,
    CitizenRegisterRequest,
    TokenRefreshRequest,
    CitizenRegisterResponse,
)

from app.repositories.user_repo import UserRepository
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.role_repo import RoleRepository

from app.exceptions.auth_expection import (
    UserAlreadyExistsException,
    InvalidCredentialException,
)

from app.utils.auth import (
    create_access_token,
    verify_password,
    get_password_hash,
    create_refresh_token,
    decode_refresh_token_or_raise,
)


router = APIRouter()


@router.post("/citizen-register", response_model=TokenResponse)
async def register(
    user_data: CitizenRegisterRequest, db: AsyncSession = Depends(get_db)
):
    try:
        user_repo = UserRepository(db)
        citizen_repo = CitizenRepository(db)
        role_repo = RoleRepository(db)
        existing_user = await user_repo.get_user_by_username(user_data.username)
        if existing_user:
            raise UserAlreadyExistsException()

        hashed_password = get_password_hash(user_data.password)
        citizen_role: Role = await role_repo.get_role_by_name("citizen")
        new_user: User = await user_repo.create_user(
            User(
                username=user_data.username,
                password_hash=hashed_password,
                role_id=citizen_role.role_id,
                status=True,
                is_verified=False,
            )
        )
        _citizen: Citizen = await citizen_repo.create_citizen(
            Citizen(
                name=user_data.name,
                user_id=new_user.user_id,
                phone_number=user_data.phone_number,
                email=user_data.email,
                home_address=user_data.home_address,
            )
        )

        access_token: str = create_access_token(data={"user_id": new_user.user_id})
        refresh_token: str = create_refresh_token(data={"user_id": new_user.user_id})
        return CitizenRegisterResponse(
            is_verified=new_user.is_verified,
            access_token=access_token,
            refresh_token=refresh_token,
            role_name="citizen",
        )
    except UserAlreadyExistsException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error occurred while registering citizen: {e}")
        raise RuntimeError("Failed to register citizen.") from e


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    user = await user_repo.get_user_by_username(credentials.username)
    if not user or not verify_password(credentials.password, user.password_hash):
        raise InvalidCredentialException()

    access_token: str = create_access_token(data={"user_id": user.user_id})
    refresh_token: str = create_refresh_token(data={"user_id": user.user_id})
    role_name: str = getattr(user.role, "role_name", "citizen")
    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, role_name=role_name
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: TokenRefreshRequest, db: AsyncSession = Depends(get_db)
):
    user_id = decode_refresh_token_or_raise(request.refresh_token)

    user_repo = UserRepository(db)
    user: User | None = await user_repo.get_user_by_id(user_id)
    if not user:
        raise InvalidCredentialException()

    access_token: str = create_access_token(data={"user_id": user.user_id})
    role_name: str = getattr(user.role, "role_name", "citizen")
    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,
        role_name=role_name,
    )
