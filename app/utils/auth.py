from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.exceptions.auth_expection import (
    InvalidCredentialException,
    InvalidTokenException,
)

secret_key = settings.JWT_SECRET
algorithm = settings.JWT_ALG
access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MIN
refresh_token_expire_minutes = settings.REFRESH_TOKEN_EXPIRE_MIN

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=refresh_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode any JWT. Raises app-level exceptions (not jwt.*).
    """
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except jwt.ExpiredSignatureError:
        raise InvalidTokenException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise InvalidCredentialException()


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
