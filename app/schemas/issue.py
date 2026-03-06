"""Issue-related enums used by API and persistence layers."""

from enum import Enum


class IssueType(str, Enum):
    """Supported issue categories."""

    ELECTRICITY = "ELECTRICITY"
    SEWAGE = "SEWAGE"


class IssueStatus(str, Enum):
    """Lifecycle states for issues."""

    REJECTED = "REJECTED"
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
