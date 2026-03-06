from __future__ import annotations

from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Optional

import aiosmtplib

from app.repositories.citizen_repo import CitizenRepository
from app.repositories.role_repo import RoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.otp import OtpChannel


class NotificationRecipient:
    def __init__(
        self,
        user_id: int,
        username: str,
        email: Optional[str] = None,
        phone_number: Optional[str] = None,
    ):
        self.user_id = user_id
        self.username = username
        self.email = email
        self.phone_number = phone_number


class BaseNotificationSender(ABC):
    @abstractmethod
    async def send(
        self, recipient: NotificationRecipient, subject: str, body: str
    ) -> None:
        pass


class EmailSender(BaseNotificationSender):
    def __init__(
        self,
        smtp_host: str = "localhost",
        smtp_port: int = 1025,
        from_email: str = "sender@battinala.com",
        smtp_user: Optional[str] = "sender@battinala.com",
        smtp_pass: Optional[str] = "password",
        start_tls: bool = True,
        validate_certs: bool = False,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_email = from_email
        self.smtp_user = smtp_user
        self.smtp_pass = smtp_pass
        self.start_tls = start_tls
        self.validate_certs = validate_certs

    async def send(
        self, recipient: NotificationRecipient, subject: str, body: str
    ) -> None:
        if not recipient.email:
            print(f"User {recipient.username} has no email. Email not sent.")
            return

        message = EmailMessage()
        message["From"] = self.from_email
        message["To"] = recipient.email
        message["Subject"] = subject
        message.set_content(body)

        await aiosmtplib.send(
            message,
            hostname=self.smtp_host,
            port=self.smtp_port,
            username=self.smtp_user,
            password=self.smtp_pass,
            start_tls=self.start_tls,
            validate_certs=self.validate_certs,
        )

        print(f"Email sent to {recipient.email}: Subject: {subject}")


class SMSSender(BaseNotificationSender):
    async def send(
        self, recipient: NotificationRecipient, subject: str, body: str
    ) -> None:
        if not recipient.phone_number:
            print(f"User {recipient.username} has no phone number. SMS not sent.")
            return

        print(f"SMS sent to {recipient.phone_number} ({recipient.username}): {body}")


class NotificationService:
    def __init__(
        self,
        user_repo: UserRepository,
        role_repo: RoleRepository,
        citizen_repo: CitizenRepository,
        email_sender: EmailSender,
        sms_sender: SMSSender,
    ):
        self.user_repo = user_repo
        self.role_repo = role_repo
        self.citizen_repo = citizen_repo
        self.senders: dict[OtpChannel, BaseNotificationSender] = {
            OtpChannel.email: email_sender,
            OtpChannel.sms: sms_sender,
        }

    async def _get_recipient(self, user_id: int) -> Optional[NotificationRecipient]:
        user = await self.user_repo.get_user_by_id(user_id)
        if not user:
            return None

        citizen = await self.citizen_repo.get_citizen_by_user_id(user_id)

        return NotificationRecipient(
            user_id=user.user_id,
            username=user.username,
            email=getattr(citizen, "email", None),
            phone_number=getattr(citizen, "phone_number", None),
        )

    async def send_to_user(
        self,
        user_id: int,
        channel: OtpChannel,
        subject: str,
        body: str,
    ) -> None:
        recipient = await self._get_recipient(user_id)
        if not recipient:
            print(f"User with ID {user_id} not found. Notification not sent.")
            return

        sender = self.senders[channel]
        await sender.send(recipient, subject, body)

    async def send_to_user_auto(
        self,
        user_id: int,
        subject: str,
        body: str,
    ) -> None:
        recipient = await self._get_recipient(user_id)
        if not recipient:
            print(f"User with ID {user_id} not found. Notification not sent.")
            return

        if recipient.email:
            await self.senders[OtpChannel.email].send(recipient, subject, body)
            return

        if recipient.phone_number:
            await self.senders[OtpChannel.sms].send(recipient, subject, body)
            return

        print(
            f"User {recipient.username} has no email or phone number. Notification not sent."
        )

    async def send_to_role(
        self,
        role_name: str,
        channel: OtpChannel,
        subject: str,
        body: str,
    ) -> None:
        role = await self.role_repo.get_role_by_name(role_name)
        if not role:
            print(f"Role '{role_name}' not found. Notification not sent.")
            return

        users = await self.role_repo.get_all_user_by_role_id(role.role_id)
        for user in users:
            await self.send_to_user(
                user_id=user.user_id,
                channel=channel,
                subject=subject,
                body=body,
            )
