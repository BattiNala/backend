"""Tests for notification service."""

# pylint: disable=protected-access

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.schemas.otp import OtpChannel
from app.services.notification_service import NotificationRecipient, NotificationService


class _RecorderSender:  # pylint: disable=too-few-public-methods
    """Test double for RecorderSender."""

    def __init__(self):
        """Init."""
        self.calls = []

    async def send(self, recipient, subject, body):
        """Send."""
        self.calls.append((recipient, subject, body))


def _service():
    """Service."""
    return NotificationService(
        user_repo=SimpleNamespace(),
        role_repo=SimpleNamespace(),
        citizen_repo=SimpleNamespace(),
        employee_repo=SimpleNamespace(),
        email_sender=_RecorderSender(),
        sms_sender=_RecorderSender(),
    )


def test_get_recipient_prefers_citizen_then_employee():
    """Test get recipient prefers citizen then employee."""
    service = _service()
    service.user_repo.get_user_by_id = AsyncMock(
        return_value=SimpleNamespace(user_id=1, username="alice")
    )
    service.citizen_repo.get_citizen_by_user_id = AsyncMock(
        return_value=SimpleNamespace(email="alice@example.com", phone_number="9800000000")
    )
    service.employee_repo.get_employee_by_user_id = AsyncMock(return_value=None)

    recipient = asyncio.run(service._get_recipient(1))

    assert recipient.email == "alice@example.com"
    assert recipient.phone_number == "9800000000"


def test_send_to_user_and_auto_route_to_expected_sender():
    """Test send to user and auto route to expected sender."""
    service = _service()
    recipient = NotificationRecipient(
        user_id=1,
        username="alice",
        email="alice@example.com",
        phone_number="9800000000",
    )
    service._get_recipient = AsyncMock(return_value=recipient)

    asyncio.run(service.send_to_user(1, OtpChannel.SMS, "subject", "body"))
    asyncio.run(service.send_to_user_auto(1, "subject", "body"))

    assert service.senders[OtpChannel.SMS].calls == [(recipient, "subject", "body")]
    assert service.senders[OtpChannel.EMAIL].calls == [(recipient, "subject", "body")]


def test_send_to_role_dispatches_to_each_user():
    """Test send to role dispatches to each user."""
    service = _service()
    service.role_repo.get_role_by_name = AsyncMock(return_value=SimpleNamespace(role_id=5))
    service.role_repo.get_all_user_by_role_id = AsyncMock(
        return_value=[SimpleNamespace(user_id=1), SimpleNamespace(user_id=2)]
    )
    service.send_to_user = AsyncMock()

    asyncio.run(service.send_to_role("staff", OtpChannel.EMAIL, "subject", "body"))

    assert service.send_to_user.await_count == 2
