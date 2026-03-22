"""Shared helpers for API v1 endpoints."""

from typing import Awaitable, Callable, TypeVar

from fastapi import HTTPException

from app.repositories.citizen_repo import CitizenRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.otp import OtpChannel
from app.services.notification_service import (
    EmailSender,
    NotificationService,
    SMSSender,
)

T = TypeVar("T")


async def with_db_error(action: Callable[[], Awaitable[T]]) -> T:
    """Run an async action and surface unexpected errors as HTTP 500s."""
    try:
        return await action()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def build_notification_service(
    user_repo: UserRepository,
    role_repo: RoleRepository,
    citizen_repo: CitizenRepository,
    employee_repo: EmployeeRepository,
) -> NotificationService:
    """Create a notification service with default email and SMS senders."""
    return NotificationService(
        user_repo=user_repo,
        role_repo=role_repo,
        citizen_repo=citizen_repo,
        employee_repo=employee_repo,
        email_sender=EmailSender(),
        sms_sender=SMSSender(),
    )


def resolve_channel_and_target(
    email: str | None,
    phone_number: str | None,
) -> tuple[str | None, OtpChannel]:
    """Resolve preferred OTP destination and channel."""
    target = email or phone_number
    channel = OtpChannel.EMAIL if email else OtpChannel.SMS
    return target, channel


async def resolve_user_contact(
    user_id: int,
    citizen_repo: CitizenRepository,
    employee_repo: EmployeeRepository,
) -> tuple[str | None, str | None]:
    """Resolve email/phone for a user, preferring email when available."""
    citizen = await citizen_repo.get_citizen_by_user_id(user_id)
    if citizen:
        return citizen.email, citizen.phone_number

    employee = await employee_repo.get_employee_by_user_id(user_id)
    if employee:
        return employee.email, employee.phone_number

    return None, None
