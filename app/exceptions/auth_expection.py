from fastapi import HTTPException


class CredentialException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(status_code=401, detail=detail)


class UserAlreadyExistsException(HTTPException):
    def __init__(self, detail: str = "Username already registered"):
        super().__init__(status_code=400, detail=detail)


class InvalidTokenException(HTTPException):
    def __init__(self, detail: str = "Invalid token"):
        super().__init__(status_code=401, detail=detail)


class InvalidCredentialException(HTTPException):
    def __init__(self, detail: str = "Invalid username or password"):
        super().__init__(status_code=401, detail=detail)
