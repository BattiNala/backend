"""Tests for conversion."""

from app.schemas.department import Department
from app.utils.conversion import department_to_issue_type


def test_department_to_issue_type_maps_fields():
    """Test department to issue type maps fields."""
    department = Department(department_id=9, department_name="Roads")

    issue_type = department_to_issue_type(department)

    assert issue_type.issue_type_id == 9
    assert issue_type.issue_type == "Roads"
