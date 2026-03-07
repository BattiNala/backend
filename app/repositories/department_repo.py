"""
Department repository for handling department-related database operations.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department


class DepartmentRepository:
    """Repository for department-related database operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_departments(self):
        """List all departments."""
        result = await self.db.execute(select(Department))
        return result.scalars().all()

    async def get_department_by_id(self, department_id: int):
        """Get a department by its ID."""
        result = await self.db.execute(
            select(Department).where(Department.department_id == department_id)
        )
        return result.scalars().first()

    async def create_department(self, department_name: str):
        """Create a new department."""
        department = Department(department_name=department_name)
        self.db.add(department)
        await self.db.commit()
        await self.db.refresh(department)
        return department

    async def get_department_by_name(self, department_name: str):
        """Get a department by its name."""
        result = await self.db.execute(
            select(Department).where(Department.department_name == department_name)
        )
        return result.scalars().first()
