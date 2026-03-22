"""
Authentication-related schema definitions for user, token, and citizen registration.
"""

from pydantic import BaseModel, Field, model_validator


class UserBase(BaseModel):
    """Base schema for user credentials."""

    username: str = Field(..., max_length=50)
    password: str = Field(..., min_length=6)


class UserCreate(UserBase):
    """Schema for creating a new user."""


class UserLogin(UserBase):
    """Schema for user login request."""


class TokenResponse(BaseModel):
    """Schema for authentication token response."""

    access_token: str
    refresh_token: str
    role_name: str = Field(..., description="Role of the user (e.g., admin, citizen, employee)")


class LoginResponse(TokenResponse):
    """Schema for login response, extending token response."""

    is_verified: bool = Field(..., description="Indicates if the user's email is verified")


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str


class TokenRefreshResponse(TokenResponse):
    """Schema for token refresh response."""


class CitizenRegisterRequest(UserCreate):
    """Schema for citizen registration request."""

    name: str = Field(..., max_length=100, description="User's full name")
    phone_number: str | None = Field(None, max_length=15, description="User's phone number")
    email: str | None = Field(None, max_length=100, description="User's email address")
    home_address: str = Field("Unknown", max_length=200, description="User's home address")

    @model_validator(mode="after")
    def check_contact(self):
        """Ensure at least one contact channel is provided."""
        if not self.phone_number and not self.email:
            raise ValueError("At least one of phone_number or email must be provided.")
        return self


class CitizenRegisterResponse(TokenResponse):
    """Schema for citizen registration response."""

    is_verified: bool = Field(..., description="Indicates if the user's email is verified")


# Password reset flows
class PasswordResetRequest(BaseModel):
    """Request a password reset OTP via email or phone."""

    username: str = Field(..., max_length=50)


class PasswordResetVerifyRequest(BaseModel):
    """Verify a password reset OTP and return a reset token."""

    username: str = Field(..., max_length=50)
    code: str


class PasswordResetVerifyResponse(BaseModel):
    """Response containing a short-lived reset token."""

    reset_token: str


class PasswordResetConfirmRequest(BaseModel):
    """Confirm password reset using the reset token."""

    reset_token: str
    new_password: str = Field(..., min_length=6)


# class JwtPayload(BaseModel):
#     user_id: int
#     role_name: str
