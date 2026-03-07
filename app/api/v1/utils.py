"""Shared helpers for API v1 endpoints."""

from typing import Awaitable, Callable, TypeVar

from fastapi import HTTPException

T = TypeVar("T")


async def with_db_error(action: Callable[[], Awaitable[T]]) -> T:
    """Run an async action and surface unexpected errors as HTTP 500s."""
    try:
        return await action()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
