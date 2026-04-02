"""
This module provides utility functions to wrap database models into
response schemas for employee and citizen profiles.
"""

from app.models.citizens import Citizen
from app.models.department import Department
from app.models.employee import Employee
from app.models.team import Team
from app.schemas.citizen import CitizenProfile
from app.schemas.employee import EmployeeProfile


def wrap_employee_profile(employee: Employee) -> EmployeeProfile:
    """Wrap an Employee object into an EmployeeProfile schema."""
    team: Team = employee.team
    department: Department = employee.department
    return EmployeeProfile(
        name=employee.name,
        email=employee.email,
        phone_number=employee.phone_number,
        team_name=team.team_name if team else None,
        department_name=department.department_name if department else None,
        current_status=employee.current_status,
    )


def wrap_citizen_profile(citizen: Citizen) -> CitizenProfile:
    """Wrap a Citizen object into a CitizenProfile schema."""
    return CitizenProfile(
        name=citizen.name,
        email=citizen.email,
        phone_number=citizen.phone_number,
        address=citizen.home_address,
        trust_score=citizen.trust_score,
    )
