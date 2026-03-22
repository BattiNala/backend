"""Department repository for handling department-related database operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.department import Department
from app.models.employee import Employee
from app.models.roles import Role
from app.models.user import User
from app.schemas.department import DepartmentAdmin


class DepartmentRepository:
    """Repository for department-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_departments(self) -> list[Department]:
        """List all departments."""
        result = await self.db.execute(select(Department))
        return result.scalars().all()

    async def get_department_by_id(self, department_id: int) -> Department | None:
        """Get a department by its ID."""
        result = await self.db.execute(
            select(Department).where(Department.department_id == department_id)
        )
        return result.scalars().first()

    async def create_department(self, department_name: str) -> Department:
        """Create a new department."""
        department = Department(department_name=department_name)
        self.db.add(department)
        await self.db.commit()
        await self.db.refresh(department)
        return department

    async def get_department_by_name(self, department_name: str) -> Department | None:
        """Get a department by its name."""
        result = await self.db.execute(
            select(Department).where(Department.department_name == department_name)
        )
        return result.scalars().first()

    async def list_department_admins(
        self, department_id: int | None = None
    ) -> list[DepartmentAdmin]:
        """List department admins, optionally filtered by department."""
        stmt = (
            select(Employee)
            .options(joinedload(Employee.department))
            .join(Employee.user)
            .join(User.role)
            .where(Role.role_name == "department_admin")
        )
        if department_id is not None:
            stmt = stmt.where(Employee.department_id == department_id)

        result = await self.db.execute(stmt)
        employees = result.scalars().all()
        return [
            DepartmentAdmin(
                employee_id=employee.employee_id,
                user_id=employee.user_id,
                department_name=employee.department.department_name,
                name=employee.name,
                email=employee.email,
                phone_number=employee.phone_number,
                team_id=employee.team_id,
            )
            for employee in employees
        ]
