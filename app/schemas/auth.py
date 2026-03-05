from pydantic import BaseModel, Field, model_validator


class UserBase(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., min_length=6)


class UserCreate(UserBase):
    pass


class UserLogin(UserBase):
    pass


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    role_name: str = Field(
        ..., description="Role of the user (e.g., admin, citizen, employee)"
    )


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(TokenResponse):
    pass


class CitizenRegisterRequest(UserCreate):
    name: str = Field(..., max_length=100, description="User's full name")
    phone_number: str | None = Field(
        None, max_length=15, description="User's phone number"
    )
    email: str | None = Field(None, max_length=100, description="User's email address")
    home_address: str = Field(
        "Unknown", max_length=200, description="User's home address"
    )

    @model_validator(mode="after")
    def check_contact(cls, values):
        if not values.phone_number and not values.email:
            raise ValueError("At least one of phone_number or email must be provided.")
        return values


class CitizenRegisterResponse(TokenResponse):
    is_verified: bool = Field(
        ..., description="Indicates if the user's email is verified"
    )


# class JwtPayload(BaseModel):
#     user_id: int
#     role_name: str
