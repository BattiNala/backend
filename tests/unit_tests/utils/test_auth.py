"""Tests for auth."""

from datetime import timedelta

import pytest

from app.exceptions.auth_expection import InvalidCredentialException, InvalidTokenException
from app.utils import auth


def test_password_hash_and_verify_round_trip():
    """Test password hash and verify round trip."""
    password = "Sup3rSecret!"

    hashed = auth.get_password_hash(password)

    assert hashed != password
    assert auth.verify_password(password, hashed) is True
    assert auth.verify_password("wrong-password", hashed) is False


def test_access_and_refresh_tokens_decode_user_id():
    """Test access and refresh tokens decode user id."""
    access_token = auth.create_access_token({"user_id": 7})
    refresh_token = auth.create_refresh_token({"user_id": 11})

    assert auth.decode_token(access_token)["user_id"] == 7
    assert auth.decode_refresh_token_or_raise(refresh_token) == 11


def test_password_reset_token_requires_expected_purpose():
    """Test password reset token requires expected purpose."""
    token = auth.create_password_reset_token({"user_id": 13})

    assert auth.decode_password_reset_token_or_raise(token) == 13

    wrong_purpose = auth.create_access_token({"user_id": 13})
    with pytest.raises(InvalidCredentialException):
        auth.decode_password_reset_token_or_raise(wrong_purpose)


def test_decode_token_raises_app_exceptions_for_invalid_and_expired_tokens():
    """Test decode token raises app exceptions for invalid and expired tokens."""
    expired = auth.create_access_token({"user_id": 1}, expires_delta=timedelta(seconds=-1))

    with pytest.raises(InvalidTokenException):
        auth.decode_token(expired)

    with pytest.raises(InvalidCredentialException):
        auth.decode_token("not-a-jwt")


def test_decode_refresh_token_requires_user_id():
    """Test decode refresh token requires user id."""
    token = auth.create_refresh_token({"scope": "refresh"})

    with pytest.raises(InvalidCredentialException):
        auth.decode_refresh_token_or_raise(token)


def test_generate_random_password_respects_length():
    """Test generate random password respects length."""
    password = auth.generate_random_password(24)

    assert len(password) == 24
    assert any(char.islower() for char in password)
    assert any(char.isupper() for char in password)
    assert any(char.isdigit() for char in password)
