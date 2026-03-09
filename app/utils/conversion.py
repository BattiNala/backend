"""Conversion utilities for the application."""

from app.schemas.department import Department
from app.schemas.issue import IssueType


def department_to_issue_type(department: Department) -> IssueType:
    return IssueType(issue_type_id=department.department_id, issue_type=department.department_name)
