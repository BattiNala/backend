"""Authentication endpoints for registration, login, token refresh, and OTP flows."""

import aiosmtplib
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.api.v1.utils import (
    build_notification_service,
    resolve_channel_and_target,
    resolve_user_contact,
)
from app.core.constants import (
    ACCOUNR_VERIFICATION_SUCCESS_EMAIL,
    CITIZEN_REGISTER_EMAIL,
    PASSWORD_RESET_EMAIL,
    PASSWORD_RESET_SUCCESS_EMAIL,
    RESEND_VERIFICATION_BODY,
)
from app.db.session import get_db
from app.exceptions.auth_expection import (
    InvalidCredentialException,
    UserAlreadyExistsException,
    UserNotFoundException,
)
from app.exceptions.otp_exception import OtpResendCooldownException
from app.models.citizens import Citizen
from app.models.roles import Role
from app.models.user import User
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.otp_repo import OtpRepository
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import (
    CitizenRegisterRequest,
    CitizenRegisterResponse,
    LoginResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetVerifyRequest,
    PasswordResetVerifyResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserLogin,
)
from app.schemas.citizen import CitizenProfile
from app.schemas.otp import OtpChannel, OtpPurpose, OtpVerificationRequest
from app.services.notification_service import (
    NotificationService,
)
from app.utils.auth import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_password_reset_token_or_raise,
    decode_refresh_token_or_raise,
    get_password_hash,
    verify_password,
)
from app.utils.otp_utils import OtpUtils

auth_router = APIRouter()
security = HTTPBearer()


async def _create_and_send_password_reset_otp(
    user: User,
    email: str | None,
    phone_number: str | None,
    otp_repo: OtpRepository,
    notification_service: NotificationService,
) -> None:
    """Deliver the reset OTP, preferring email and falling back to SMS when needed."""
    delivery_attempts: list[tuple[OtpChannel, str]] = []
    if email:
        delivery_attempts.append((OtpChannel.EMAIL, email))
    if phone_number:
        delivery_attempts.append((OtpChannel.SMS, phone_number))

    if not delivery_attempts:
        raise ValueError("User has no email or phone number.")

    otp_code, otp_salt, otp_hash = OtpUtils.handle_otp_generation()
    last_error: Exception | None = None

    for channel, target in delivery_attempts:
        otp_record = await otp_repo.create_otp_code(
            user_id=user.user_id,
            channel=channel,
            target=target,
            purpose=OtpPurpose.RESET_PASSWORD,
            otp_salt=otp_salt,
            otp_hash=otp_hash,
        )
        try:
            await notification_service.send_to_user(
                user_id=user.user_id,
                channel=channel,
                subject="Battinala Password Reset OTP",
                body=PASSWORD_RESET_EMAIL.format(username=user.username, otp_code=otp_code),
            )
            return
        except (aiosmtplib.errors.SMTPException, OSError) as exc:
            last_error = exc
            await otp_repo.delete_otp_code(otp_record.otp_id)

    if last_error:
        raise last_error


async def _create_signup_otp_and_notify(
    user: User,
    user_data: CitizenRegisterRequest,
    otp_repo: OtpRepository,
    notification_service: NotificationService,
) -> None:
    """Create a signup OTP and send it to the user's preferred channel."""
    otp_code, otp_salt, otp_hash = OtpUtils.handle_otp_generation()
    target, channel = resolve_channel_and_target(
        user_data.email,
        user_data.phone_number,
    )

    await otp_repo.create_otp_code(
        user_id=user.user_id,
        channel=channel,
        target=target,
        purpose=OtpPurpose.SIGNUP,
        otp_salt=otp_salt,
        otp_hash=otp_hash,
    )

    await notification_service.send_to_user_auto(
        user_id=user.user_id,
        subject="Welcome to Battinala!",
        body=CITIZEN_REGISTER_EMAIL.format(name=user_data.name, otp_code=otp_code),
    )


@auth_router.post(
    "/citizen-register", response_model=CitizenRegisterResponse, status_code=status.HTTP_201_CREATED
)
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
        employee_repo = EmployeeRepository(db)
        notification_service = build_notification_service(
            user_repo=user_repo,
            role_repo=role_repo,
            citizen_repo=citizen_repo,
            employee_repo=employee_repo,
        )

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
        await _create_signup_otp_and_notify(
            user=new_user,
            user_data=user_data,
            otp_repo=otp_repo,
            notification_service=notification_service,
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
        employee_repo = EmployeeRepository(db)

        existing_otp = await otp_repo.get_otp_code_by_user_id(
            current_user.user_id, purpose=OtpPurpose.SIGNUP
        )
        if existing_otp:
            available, time_remaining = OtpUtils.is_resend_available(
                existing_otp.resend_available_at
            )
            if not available:
                raise OtpResendCooldownException(time_remaining)

            await otp_repo.delete_otp_code(existing_otp.otp_id)

        otp_code, otp_salt, otp_hash = OtpUtils.handle_otp_generation()

        target_user = await user_repo.get_user_with_citizen_profile(current_user.user_id)
        profile: CitizenProfile | None = target_user.citizen_profile if target_user else None

        if not profile:
            raise ValueError("User profile not found.")

        target, channel = resolve_channel_and_target(
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

        body = RESEND_VERIFICATION_BODY.format(username=current_user.username, otp_code=otp_code)

        await build_notification_service(
            user_repo=user_repo,
            role_repo=role_repo,
            citizen_repo=citizen_repo,
            employee_repo=employee_repo,
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
        employee_repo = EmployeeRepository(db)

        otp_details = await otp_repo.get_otp_code_by_user_id(
            current_user.user_id, purpose=OtpPurpose.SIGNUP
        )
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

        await build_notification_service(
            user_repo=user_repo,
            role_repo=role_repo,
            citizen_repo=citizen_repo,
            employee_repo=employee_repo,
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


@auth_router.post("/password-reset/request")
async def request_password_reset(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset OTP to the user's preferred contact channel."""
    try:
        user_repo = UserRepository(db)
        role_repo = RoleRepository(db)
        citizen_repo = CitizenRepository(db)
        employee_repo = EmployeeRepository(db)
        otp_repo = OtpRepository(db)

        user = await user_repo.get_user_by_username(request.username)
        if not user:
            raise UserNotFoundException()

        email, phone_number = await resolve_user_contact(user.user_id, citizen_repo, employee_repo)

        existing_otp = await otp_repo.get_otp_code_by_user_id(
            user.user_id, purpose=OtpPurpose.RESET_PASSWORD
        )
        if existing_otp:
            available, time_remaining = OtpUtils.is_resend_available(
                existing_otp.resend_available_at
            )
            if not available:
                raise OtpResendCooldownException(time_remaining)
            await otp_repo.delete_otp_code(existing_otp.otp_id)

        notification_service = build_notification_service(
            user_repo=user_repo,
            role_repo=role_repo,
            citizen_repo=citizen_repo,
            employee_repo=employee_repo,
        )
        await _create_and_send_password_reset_otp(
            user=user,
            email=email,
            phone_number=phone_number,
            otp_repo=otp_repo,
            notification_service=notification_service,
        )

        return {"message": "Password reset OTP sent successfully."}

    except OtpResendCooldownException:
        raise
    except UserNotFoundException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error during password reset request: {e}")
        raise RuntimeError("Failed to send password reset OTP.") from e


@auth_router.post("/password-reset/verify", response_model=PasswordResetVerifyResponse)
async def verify_password_reset(
    request: PasswordResetVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify a password reset OTP and return a reset token."""
    try:
        user_repo = UserRepository(db)
        otp_repo = OtpRepository(db)

        user = await user_repo.get_user_by_username(request.username)
        if not user:
            raise UserNotFoundException()

        otp_details = await otp_repo.get_otp_code_by_user_id(
            user.user_id, purpose=OtpPurpose.RESET_PASSWORD
        )
        if not otp_details:
            raise HTTPException(status_code=404, detail="OTP not found.")

        if not OtpUtils.verify_otp(
            request.code,
            otp_details.otp_salt,
            otp_details.otp_hash,
            otp_details.expires_at,
        ):
            raise ValueError("Invalid OTP.")

        await otp_repo.consume_otp_code(otp_details.otp_id)

        reset_token = create_password_reset_token({"user_id": user.user_id})
        return PasswordResetVerifyResponse(reset_token=reset_token)

    except Exception as e:
        await db.rollback()
        print(f"Error during password reset verification: {e}")
        raise RuntimeError("Failed to verify password reset OTP.") from e


@auth_router.post("/password-reset/confirm")
async def confirm_password_reset(
    request: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm password reset using a valid reset token."""
    try:
        user_repo = UserRepository(db)
        role_repo = RoleRepository(db)
        citizen_repo = CitizenRepository(db)
        employee_repo = EmployeeRepository(db)

        user_id = decode_password_reset_token_or_raise(request.reset_token)
        user = await user_repo.get_user_by_id(user_id)
        if not user:
            raise InvalidCredentialException()

        await user_repo.update_password(user.user_id, get_password_hash(request.new_password))

        await build_notification_service(
            user_repo=user_repo,
            role_repo=role_repo,
            citizen_repo=citizen_repo,
            employee_repo=employee_repo,
        ).send_to_user_auto(
            user_id=user.user_id,
            subject="Battinala Password Reset Successful",
            body=PASSWORD_RESET_SUCCESS_EMAIL.format(username=user.username),
        )

        return {"message": "Password reset successfully."}

    except InvalidCredentialException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error during password reset confirmation: {e}")
        raise RuntimeError("Failed to confirm password reset.") from e
