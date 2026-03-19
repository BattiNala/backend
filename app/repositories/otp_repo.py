"""Repository helpers for OTP code lifecycle operations."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.otp_code import OtpChannel, OtpCode, OtpPurpose


class OtpRepository:
    """Data-access operations for one-time password codes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Keep explicit parameters for call-site clarity in auth flows.
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    async def create_otp_code(
        self,
        user_id: int,
        channel: OtpChannel,
        target: str,
        purpose: OtpPurpose,
        otp_salt: bytes,
        otp_hash: bytes,
        expires_in_minutes: int = 10,
        resend_cooldown_minutes: int = 2,
    ) -> OtpCode:
        """Create and persist a new OTP code with expiry and resend windows."""
        new_otp = OtpCode(
            otp_id=uuid4(),
            user_id=user_id,
            channel=channel,
            target=target,
            purpose=purpose,
            otp_salt=otp_salt,
            otp_hash=otp_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
            resend_available_at=datetime.now(timezone.utc)
            + timedelta(minutes=resend_cooldown_minutes),
        )
        self.db.add(new_otp)
        await self.db.commit()
        await self.db.refresh(new_otp)
        return new_otp

    async def get_otp_code_by_user_id(
        self, user_id: int, purpose: OtpPurpose | None = None
    ) -> OtpCode:
        """Return the OTP record associated with a user, optionally filtered by purpose."""
        stmt = select(OtpCode).options(selectinload(OtpCode.user)).where(OtpCode.user_id == user_id)
        if purpose:
            stmt = stmt.where(OtpCode.purpose == purpose)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def delete_otp_code(self, otp_id: uuid4):
        """Delete an OTP record by id when it exists."""
        result = await self.db.execute(select(OtpCode).where(OtpCode.otp_id == otp_id))
        otp_code = result.scalars().first()
        if otp_code:
            await self.db.delete(otp_code)
            await self.db.commit()

    async def delete_expired_otps(self):
        """Delete all OTP records that are already expired."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(select(OtpCode).where(OtpCode.expires_at < now))
        expired_otps = result.scalars().all()
        for otp in expired_otps:
            await self.db.delete(otp)
        await self.db.commit()

    async def consume_otp_code(self, otp_id: uuid4):
        """Mark an OTP as consumed and return the updated record."""
        result = await self.db.execute(
            select(OtpCode).options(selectinload(OtpCode.user)).where(OtpCode.otp_id == otp_id)
        )
        otp_code = result.scalars().first()
        if otp_code:
            otp_code.consumed_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(otp_code)
            return otp_code
        return None
