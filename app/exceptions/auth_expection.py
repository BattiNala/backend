"""
Custom exceptions for authentication-related errors.
"""

from fastapi import HTTPException


class CredentialException(HTTPException):
    """Exception raised when there is an issue with user credentials."""

    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(status_code=401, detail=detail)


class UserAlreadyExistsException(HTTPException):
    """
    Exception raised when trying to register a user that already exists.
    """

    def __init__(self, detail: str = "Username already registered"):
        super().__init__(status_code=400, detail=detail)


class InvalidTokenException(HTTPException):
    """Exception raised when an invalid token is provided."""

    def __init__(self, detail: str = "Invalid token"):
        super().__init__(status_code=401, detail=detail)


class InvalidCredentialException(HTTPException):
    """Exception raised when invalid credentials are provided."""

    def __init__(self, detail: str = "Invalid username or password"):
        super().__init__(status_code=401, detail=detail)


class UserNotFoundException(HTTPException):
    """Exception raised when a user is not found."""

    def __init__(self, detail: str = "User not found"):
        super().__init__(status_code=404, detail=detail)
