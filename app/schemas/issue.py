"""Issue-related enums used by API and persistence layers."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field, model_validator


class IssuePriority(str, Enum):
    """Priority levels for issues."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


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
    issue_priority: IssuePriority = IssuePriority.NORMAL
    latitude: float
    longitude: float

    @model_validator(mode="before")
    @classmethod
    def validate_contact_no(cls, values):
        """Validate that contact_no is provided for anonymous issues."""
        if values.get("is_anonymous") and not values.get("contact_no"):
            raise ValueError("contact_no is required for anonymous issues")
        return values

    model_config = {
        "json_schema_extra": {
            "example": {
                "description": "Pothole on Main Street",
                "issue_type": 1,
                "issue_priority": "HIGH",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "issue_location": "Main Street near 5th Avenue",
                "contact_no": "9801234567",
            }
        }
    }


class IssueCreate(IssueBase):
    """Schema for creating a new issue."""

    latitude: float
    issue_priority: IssuePriority = IssuePriority.NORMAL
    longitude: float
    issue_location: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "issue_type": 1,
                "description": "Example description",
                "latitude": 27.7172,
                "longitude": 85.3240,
                "issue_priority": "NORMAL",
                "issue_location": "Kathmandu",
            }
        }
    }


class IssueCreateResponse(BaseModel):
    """Response model for an issue."""

    issue_label: str
    status: IssueStatus
    created_at: str


class AnonymousIssueCreateResponse(IssueCreateResponse):
    """Response model for an anonymous issue."""


class IssueListItem(BaseModel):
    """Schema for listing issues."""

    issue_label: str
    issue_priority: IssuePriority
    issue_type: str
    description: str
    status: IssueStatus
    created_at: str


class IssueListResponse(BaseModel):
    """Response model for listing issues."""

    items: list[IssueListItem] = Field(validation_alias=AliasChoices("items", "issues"))
    total: int

    @property
    def issues(self) -> list[IssueListItem]:
        """Backward-compatible accessor for older callers."""
        return self.items


class IssueDetailResponse(BaseModel):
    """Response model for issue details."""

    issue_label: str
    issue_type: str
    issue_priority: IssuePriority
    description: str
    status: IssueStatus
    issue_priority: IssuePriority
    assigned_to: Optional[str] = None
    created_at: str
    attachments: list[str]  # List of attachment URLs
    rejected_reason: Optional[str] = None
    issue_location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class IssueStatusUpdate(BaseModel):
    """Schema for updating an issue status."""

    issue_label: str
    status: IssueStatus


class IssueReportRequest(BaseModel):
    """Schema for reporting a false issue."""

    issue_label: str
    reason: str = Field(..., min_length=30)


class IssuePriorityOptionsResponse(BaseModel):
    """Response model for issue priority options."""

    priorities: list[IssuePriority]


class IssueRejectRequest(BaseModel):
    """Schema for rejecting an issue."""

    issue_label: str
    reason: str = Field(..., min_length=30)


class IssueRejectResponse(BaseModel):
    """Response model for issue rejection."""

    message: str
    status: IssueStatus


@dataclass(slots=True)
class IssueListFilters:
    """Optional filters for listing issues."""

    status: IssueStatus | None = None
    priority: IssuePriority | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    department_id: int | None = None
    assignee_id: int | None = None
    reporter_id: int | None = None
