"""Authentication endpoints for registration, login, token refresh, and OTP flows."""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.constants import ACCOUNR_VERIFICATION_SUCCESS_EMAIL, CITIZEN_REGISTER_EMAIL
from app.db.session import get_db
from app.exceptions.auth_expection import (
    InvalidCredentialException,
    UserAlreadyExistsException,
)
from app.exceptions.otp_exception import OtpResendCooldownException
from app.models.citizens import Citizen
from app.models.roles import Role
from app.models.user import User
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.otp_repo import OtpRepository
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    CitizenRegisterRequest,
    CitizenRegisterResponse,
    LoginResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserLogin,
)
from app.schemas.otp import OtpChannel, OtpPurpose, OtpVerificationRequest
from app.services.notification_service import (
    EmailSender,
    NotificationService,
    SMSSender,
)
from app.utils.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token_or_raise,
    get_password_hash,
    verify_password,
)
from app.utils.otp_utils import OtpUtils

auth_router = APIRouter()
security = HTTPBearer()


def _build_notification_service(
    user_repo: UserRepository,
    role_repo: RoleRepository,
    citizen_repo: CitizenRepository,
) -> NotificationService:
    """Create a notification service with default email and SMS senders."""
    return NotificationService(
        user_repo=user_repo,
        role_repo=role_repo,
        citizen_repo=citizen_repo,
        email_sender=EmailSender(),
        sms_sender=SMSSender(),
    )


def _resolve_channel_and_target(
    email: str | None,
    phone_number: str | None,
) -> tuple[str | None, OtpChannel]:
    """Resolve preferred OTP destination and channel."""
    target = email or phone_number
    channel = OtpChannel.EMAIL if email else OtpChannel.SMS
    return target, channel


@auth_router.post("/citizen-register", response_model=TokenResponse)
async def register(
    user_data: CitizenRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register a citizen user and send an OTP verification code."""
    try:
        user_repo = UserRepository(db)
        citizen_repo = CitizenRepository(db)
        role_repo = RoleRepository(db)
        otp_repo = OtpRepository(db)

        existing_user = await user_repo.get_user_by_username(user_data.username)
        if existing_user:
            raise UserAlreadyExistsException()

        citizen_role: Role = await role_repo.get_role_by_name("citizen")
        new_user: User = await user_repo.create_user(
            User(
                username=user_data.username,
                password_hash=get_password_hash(user_data.password),
                role_id=citizen_role.role_id,
                status=True,
                is_verified=False,
            )
        )

        await citizen_repo.create_citizen(
            Citizen(
                name=user_data.name,
                user_id=new_user.user_id,
                phone_number=user_data.phone_number,
                email=user_data.email,
                home_address=user_data.home_address or "Unspecified",
            )
        )
        otp_code, otp_salt, otp_hash = OtpUtils.handle_otp_generation()
        target, channel = _resolve_channel_and_target(
            user_data.email,
            user_data.phone_number,
        )

        await otp_repo.create_otp_code(
            user_id=new_user.user_id,
            channel=channel,
            target=target,
            purpose=OtpPurpose.SIGNUP,
            otp_salt=otp_salt,
            otp_hash=otp_hash,
        )

        await _build_notification_service(
            user_repo=user_repo,
            role_repo=role_repo,
            citizen_repo=citizen_repo,
        ).send_to_user_auto(
            user_id=new_user.user_id,
            subject="Welcome to Battinala!",
            body=CITIZEN_REGISTER_EMAIL.format(name=user_data.name, otp_code=otp_code),
        )

        return CitizenRegisterResponse(
            is_verified=new_user.is_verified,
            access_token=create_access_token(data={"user_id": new_user.user_id}),
            refresh_token=create_refresh_token(data={"user_id": new_user.user_id}),
            role_name="citizen",
        )

    except UserAlreadyExistsException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error occurred while registering citizen: {e}")
        raise RuntimeError("Failed to register citizen.") from e


@auth_router.post("/login", response_model=LoginResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and return access
    and refresh tokens along with role information.
    """
    user_repo = UserRepository(db)
    user = await user_repo.get_user_by_username(credentials.username)
    if not user or not verify_password(credentials.password, user.password_hash):
        raise InvalidCredentialException()

    access_token: str = create_access_token(data={"user_id": user.user_id})
    refresh_jwt: str = create_refresh_token(data={"user_id": user.user_id})
    role_name: str = getattr(user.role, "role_name", "citizen")
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_jwt,
        role_name=role_name,
        is_verified=user.is_verified,
    )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(request: TokenRefreshRequest, db: AsyncSession = Depends(get_db)):
    """Issue a new access token using a valid refresh token."""
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


@auth_router.post("/resend-verification")
# Keep explicit intermediate values for readability of OTP cooldown flow.
# pylint: disable=too-many-locals
async def resend_verification_email(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resend a signup OTP when the cooldown window allows it."""
    try:
        if current_user.is_verified:
            return {"message": "User is already verified."}

        user_repo = UserRepository(db)
        otp_repo = OtpRepository(db)
        role_repo = RoleRepository(db)
        citizen_repo = CitizenRepository(db)

        existing_otp = await otp_repo.get_otp_code_by_user_id(current_user.user_id)
        if existing_otp:
            available, time_remaining = OtpUtils.is_resend_available(
                existing_otp.resend_available_at
            )
            if not available:
                raise OtpResendCooldownException(time_remaining)

            await otp_repo.delete_otp_code(existing_otp.otp_id)

        otp_code, otp_salt, otp_hash = OtpUtils.handle_otp_generation()

        target_user = await user_repo.get_user_with_citizen_profile(current_user.user_id)
        profile = target_user.citizen_profile if target_user else None

        if not profile:
            raise ValueError("User profile not found.")

        target, channel = _resolve_channel_and_target(
            profile.email,
            profile.phone_number,
        )
        if target is None:
            raise ValueError("User has no email or phone number.")

        await otp_repo.create_otp_code(
            user_id=current_user.user_id,
            channel=channel,
            target=target,
            purpose=OtpPurpose.SIGNUP,
            otp_salt=otp_salt,
            otp_hash=otp_hash,
        )

        body = (
            f"Hello {current_user.username},\n\n"
            f"Use the code {otp_code} to verify your Battinala account.\n\n"
            f"Best regards,\n"
            f"Battinala Team"
        )

        await _build_notification_service(
            user_repo=user_repo,
            role_repo=role_repo,
            citizen_repo=citizen_repo,
        ).send_to_user(
            user_id=current_user.user_id,
            channel=channel,
            subject="Battinala Account Verification Reminder",
            body=body,
        )

        return {"message": "Verification code resent successfully."}

    except OtpResendCooldownException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error occurred while resending verification code: {e}")
        raise RuntimeError("Failed to resend verification code.") from e


@auth_router.post("/verify")
async def verify_user(
    request: OtpVerificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate the submitted OTP and mark the current user as verified."""
    try:
        if current_user.is_verified:
            return {"message": "User is already verified."}

        user_repo = UserRepository(db)
        otp_repo = OtpRepository(db)
        role_repo = RoleRepository(db)
        citizen_repo = CitizenRepository(db)

        otp_details = await otp_repo.get_otp_code_by_user_id(current_user.user_id)
        if not otp_details:
            raise ValueError("OTP not found.")

        if not OtpUtils.verify_otp(
            request.code,
            otp_details.otp_salt,
            otp_details.otp_hash,
            otp_details.expires_at,
        ):
            raise ValueError("Invalid OTP.")

        await user_repo.verify_user(current_user.user_id)
        await otp_repo.consume_otp_code(otp_details.otp_id)

        await _build_notification_service(
            user_repo=user_repo,
            role_repo=role_repo,
            citizen_repo=citizen_repo,
        ).send_to_user_auto(
            user_id=current_user.user_id,
            subject="Your Battinala Account is Verified!",
            body=ACCOUNR_VERIFICATION_SUCCESS_EMAIL.format(username=current_user.username),
        )

        return {"message": "User verified successfully."}

    except Exception as e:
        await db.rollback()
        print(f"Error during user verification: {e}")
        raise RuntimeError("Failed to verify user.") from e
