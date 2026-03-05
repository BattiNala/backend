from pydantic import BaseModel


class LoginSuccessResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    role_name: str
    is_verified: bool
    status: bool


class LoginFailureResponse(BaseModel):
    detail: str
