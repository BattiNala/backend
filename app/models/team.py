# pylint: disable=duplicate-code

"""Team model definition."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class Team(Base):  # pylint: disable=too-few-public-methods,duplicate-code
    """
    Model representing a team of employees responsible for handling issues.
    Each team belongs to a department and has a base location with a coverage radius.
    The team's availability status is determined by the availability of its members."""

    __tablename__ = "teams"

    team_id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String(100), nullable=False, unique=True)

    # availibility status of the team based on the availability of its members
    # if all members are busy, then the team is considered busy.
    # If at least one member is available,
    # the team is considered available.
    status = Column(Boolean, nullable=False, default=True)
    department_id = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_latitude = Column(Numeric(8, 4), nullable=False)
    base_longitude = Column(Numeric(8, 4), nullable=False)
    coverage_radius_km = Column(Integer, nullable=False)

    members = relationship(
        "Employee",
        back_populates="team",
        cascade="all, delete",
    )

    department = relationship("Department", back_populates="teams", foreign_keys=[department_id])

    def __repr__(self):
        return f"""
        <Team(team_id={self.team_id},team_name='{self.team_name}', status='{self.status}')>
        """
