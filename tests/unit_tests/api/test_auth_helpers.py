"""Tests for auth helpers."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api.v1.utils import (
    build_notification_service,
    resolve_channel_and_target,
    resolve_user_contact,
)
from app.schemas.otp import OtpChannel
from app.services.notification_service import EmailSender, NotificationService, SMSSender


def test_build_notification_service_wires_expected_sender_types():
    """Test build notification service wires expected sender types."""
    service = build_notification_service(
        user_repo=SimpleNamespace(),
        role_repo=SimpleNamespace(),
        citizen_repo=SimpleNamespace(),
        employee_repo=SimpleNamespace(),
    )

    assert isinstance(service, NotificationService)
    assert isinstance(service.senders[OtpChannel.EMAIL], EmailSender)
    assert isinstance(service.senders[OtpChannel.SMS], SMSSender)


def test_resolve_channel_and_target_prefers_email_then_sms():
    """Test resolve channel and target prefers email then sms."""
    assert resolve_channel_and_target("a@example.com", "9800") == (
        "a@example.com",
        OtpChannel.EMAIL,
    )
    assert resolve_channel_and_target(None, "9800") == ("9800", OtpChannel.SMS)


def test_resolve_user_contact_prefers_citizen_then_employee():
    """Test resolve user contact prefers citizen then employee."""
    citizen_repo = SimpleNamespace(
        get_citizen_by_user_id=AsyncMock(
            return_value=SimpleNamespace(email="citizen@example.com", phone_number="9800")
        )
    )
    employee_repo = SimpleNamespace(get_employee_by_user_id=AsyncMock(return_value=None))

    assert asyncio.run(resolve_user_contact(1, citizen_repo, employee_repo)) == (
        "citizen@example.com",
        "9800",
    )

    citizen_repo.get_citizen_by_user_id = AsyncMock(return_value=None)
    employee_repo.get_employee_by_user_id = AsyncMock(
        return_value=SimpleNamespace(email="employee@example.com", phone_number="9811")
    )

    assert asyncio.run(resolve_user_contact(2, citizen_repo, employee_repo)) == (
        "employee@example.com",
        "9811",
    )
