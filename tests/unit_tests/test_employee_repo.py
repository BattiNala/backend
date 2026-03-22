"""Tests for employee repository."""

# pylint: disable=too-few-public-methods
import asyncio
from types import SimpleNamespace

from app.repositories.employee_repo import EmployeeRepository


class _FakeResult:
    """Minimal execute result test double."""

    def __init__(self, employee):
        self._employee = employee

    def scalar_one_or_none(self):
        """Return the configured employee."""
        return self._employee


class _FakeSession:
    """Minimal async session test double."""

    def __init__(self, employee):
        self._employee = employee

    async def execute(self, _stmt):
        """Return a fake query result."""
        return _FakeResult(self._employee)


def test_get_employee_profile_by_user_id_returns_employee_model():
    """Profile lookup returns the loaded employee entity for endpoint serialization."""
    employee = SimpleNamespace(
        name="User 1",
        email="user1@example.com",
        phone_number="9800000000",
        current_status="busy",
        team=SimpleNamespace(
            team_name="Roads",
            department=SimpleNamespace(department_name="Infrastructure"),
        ),
    )
    repo = EmployeeRepository(_FakeSession(employee))

    result = asyncio.run(repo.get_employee_profile_by_user_id(7))

    assert result is employee
