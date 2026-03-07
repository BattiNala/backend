"""Issue-related enums used by API and persistence layers."""

from enum import Enum

from pydantic import BaseModel


class IssueStatus(str, Enum):
    """Lifecycle states for issues."""

    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    REJECTED = "REJECTED"
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class IssueType(BaseModel):
    """Types of issues that can be reported, mapped to department IDs."""

    issue_type: str
    issue_type_id: int


class IssueBase(BaseModel):
    """Base schema for issue information."""

    issue_type: int
    description: str
    is_anonymous: bool = False


class AnonymousIssueCreate(IssueBase):
    """Schema for creating a new anonymous issue."""


class IssueCreate(IssueBase):
    """Schema for creating a new issue."""

    status: IssueStatus = IssueStatus.OPEN
