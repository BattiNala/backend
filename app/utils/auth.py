"""
Authentication utility functions for password hashing, JWT creation, and decoding.
"""

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.exceptions.auth_expection import (
    InvalidCredentialException,
    InvalidTokenException,
)

SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALG
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MIN
REFRESH_TOKEN_EXPIRE_MINUTES = settings.REFRESH_TOKEN_EXPIRE_MIN
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = settings.PASSWORD_RESET_TOKEN_EXPIRE_MIN

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash the password using Argon2 and return the hash string."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify the plain password against the hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token with the given data and expiration.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT refresh token with the given data and expiration.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_password_reset_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a short-lived JWT for password reset confirmation.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "purpose": "password_reset"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode any JWT. Raises app-level exceptions (not jwt.*).
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenException(detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidCredentialException() from exc


def decode_refresh_token_or_raise(token: str) -> int:
    """
    Refresh-token specific decode helper.
    Returns user_id or raises your app exception/HTTPException.
    """
    payload = decode_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise InvalidCredentialException()
    return int(user_id)


def decode_password_reset_token_or_raise(token: str) -> int:
    """
    Password reset token decode helper.
    Returns user_id or raises your app exception/HTTPException.
    """
    payload = decode_token(token)
    if payload.get("purpose") != "password_reset":
        raise InvalidCredentialException()
    user_id = payload.get("user_id")
    if not user_id:
        raise InvalidCredentialException()
    return int(user_id)


def generate_random_password(length: int = 12) -> str:
    """Generate a random password of the specified length."""

    alphabet = string.ascii_letters + string.digits + string.punctuation
    return "".join(secrets.choice(alphabet) for _ in range(length))
