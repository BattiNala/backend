"""Issue-related enums used by API and persistence layers."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, model_validator


class IssueStatus(str, Enum):
    """Lifecycle states for issues."""

    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    REJECTED = "REJECTED"
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class IssueType(BaseModel):
    """Types of issues that can be reported, mapped to department IDs."""

    issue_type_id: int
    issue_type: str


class IssueTypesList(BaseModel):
    """Response model for listing issue types."""

    types: list[IssueType]


class IssueBase(BaseModel):
    """Base schema for issue information."""

    issue_type: int
    description: str
    # is_anonymous: bool = False


class AnonymousIssueCreate(IssueBase):
    """Schema for creating a new anonymous issue."""

    contact_no: str
    issue_location: Optional[str] = None
    latitude: float
    longitude: float

    @model_validator(mode="before")
    @classmethod
    def validate_contact_no(cls, values):
        """Validate that contact_no is provided for anonymous issues."""
        if values.get("is_anonymous") and not values.get("contact_no"):
            raise ValueError("contact_no is required for anonymous issues")
        return values


class IssueCreate(IssueBase):
    """Schema for creating a new issue."""

    status: IssueStatus = IssueStatus.OPEN
    latitude: float
    longitude: float
    issue_location: Optional[str] = None


class IssueCreateResponse(BaseModel):
    """Response model for an issue."""

    issue_label: str
    status: IssueStatus
    created_at: str


class AnonymousIssueCreateResponse(IssueCreateResponse):
    """Response model for an anonymous issue."""
