"""
Employee repository for handling database operations related to employees.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.employee import Employee


class EmployeeRepository:
    """Repository for employee-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db: AsyncSession = db

    async def create_employee(self, employee: Employee) -> Employee:
        """Create a new employee in the database."""
        self.db.add(employee)
        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    async def get_employee_profile_by_user_id(self, user_id: int) -> Employee | None:
        """Get an employee by user ID with team and department eagerly loaded."""
        stmt = (
            select(Employee)
            .options(joinedload(Employee.team), joinedload(Employee.department))
            .where(Employee.user_id == user_id)
        )

        result = await self.db.execute(stmt)
        employee: Employee = result.scalar_one_or_none()

        if not employee:
            return None

        return employee

    async def get_employee_by_user_id(self, user_id: int) -> Employee | None:
        """Get an employee by their user ID."""
        stmt = select(Employee).where(Employee.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_employees_by_department(self, department_id: int) -> list[Employee]:
        """Get all employees belonging to a specific department."""
        stmt = (
            select(Employee)
            .where(Employee.department_id == department_id)
            .options(joinedload(Employee.team), joinedload(Employee.department))
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
