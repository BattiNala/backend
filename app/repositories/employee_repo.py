"""
Employee repository for handling database operations related to employees.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.department import Department
from app.models.employee import Employee
from app.models.team import Team
from app.schemas.employee import EmployeeProfile


class EmployeeRepository:
    def __init__(self, db: AsyncSession):
        self.db: AsyncSession = db

    async def create_employee(self, employee: Employee) -> Employee:
        """Create a new employee in the database."""
        self.db.add(employee)
        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def get_employee_profile_by_user_id(self, user_id: int) -> dict | None:
        stmt = (
            select(Employee)
            .options(
                joinedload(Employee.teams).joinedload(  # load team
                    Team.department
                )  # load department through team
            )
            .where(Employee.user_id == user_id)
        )

        result = await self.db.execute(stmt)
        employee: Employee = result.scalar_one_or_none()

        if not employee:
            return None

        team: Team = employee.teams
        department: Department = team.department if team else None

        return EmployeeProfile(
            name=employee.name,
            email=employee.email,
            phone_number=employee.phone_number,
            team_name=team.team_name if team else None,
            department_name=department.department_name if department else None,
            status=employee.current_status,
        )
