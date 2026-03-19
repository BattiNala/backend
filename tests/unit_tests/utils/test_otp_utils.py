"""Tests for otp utils."""

from datetime import datetime, timedelta, timezone

import pytest

from app.utils.otp_utils import OtpUtils


def test_handle_otp_generation_returns_code_salt_and_hash():
    """Test handle otp generation returns code salt and hash."""
    code, salt, otp_hash = OtpUtils.handle_otp_generation(otp_length=6)

    assert len(code) == 6
    assert code.isdigit()
    assert isinstance(salt, bytes)
    assert isinstance(otp_hash, bytes)
    assert OtpUtils.verify_otp(
        code,
        salt,
        otp_hash,
        datetime.now(timezone.utc) + timedelta(minutes=1),
    )


def test_generate_otp_rejects_non_positive_length():
    """Test generate otp rejects non positive length."""
    with pytest.raises(ValueError):
        OtpUtils.generate_otp(0)


def test_hash_otp_accepts_str_and_bytes():
    """Test hash otp accepts str and bytes."""
    salt = OtpUtils.generate_salt()

    assert OtpUtils.hash_otp("123456", salt) == OtpUtils.hash_otp(b"123456", salt)


def test_verify_otp_returns_false_for_expired_or_invalid_code():
    """Test verify otp returns false for expired or invalid code."""
    salt = OtpUtils.generate_salt()
    stored_hash = OtpUtils.hash_otp("654321", salt)

    assert (
        OtpUtils.verify_otp(
            "654321",
            salt,
            stored_hash,
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        is False
    )
    assert (
        OtpUtils.verify_otp(
            "000000",
            salt,
            stored_hash,
            datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        is False
    )


def test_is_resend_available_returns_remaining_seconds():
    """Test is resend available returns remaining seconds."""
    available, remaining = OtpUtils.is_resend_available(
        datetime.now(timezone.utc) + timedelta(seconds=30)
    )

    assert available is False
    assert 0 < remaining <= 30

    available, remaining = OtpUtils.is_resend_available(
        datetime.now(timezone.utc) - timedelta(seconds=1)
    )

    assert available is True
    assert remaining == 0
