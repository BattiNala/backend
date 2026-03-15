"""
Validator functions for input validation.
"""

from fastapi import HTTPException, Request, UploadFile

from app.utils.user_agent import get_device_type

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def ensure_required_user_agent(request: Request, required_agent: str) -> None:
    """Ensure that the User-Agent header matches the required agent type."""
    user_agent = request.headers.get("user-agent")
    if not user_agent:
        raise HTTPException(
            status_code=400,
            detail="User-Agent header is required to create anonymous issues.",
        )
    user_agent_check = get_device_type(user_agent)
    if user_agent_check != required_agent:
        raise HTTPException(
            status_code=400,
            detail=f"Only {required_agent} user agents are allowed to create anonymous issues.",
        )


def validate_photos(photos: list[UploadFile]) -> None:
    """Validate that at least one photo is provided and that all photos are of allowed types."""
    if not photos:
        raise HTTPException(
            status_code=400,
            detail="At least one photo is required",
        )
    for photo in photos:
        if photo.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Only JPEG, PNG, and WebP image files are allowed",
            )
