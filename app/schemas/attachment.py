"""Schema definitions for attachment-related operations."""

from typing import TypedDict


class AttachmentCreatePayload(TypedDict):
    """Structured payload for creating an attachment."""

    path: str
    phash: str | None
