from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class Team(Base):
    __tablename__ = "teams"

    team_id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String(100), nullable=False, unique=True)

    # availibility status of the team based on the availability of its members
    # if all members are busy, then the team is considered busy. If at least one member is available,
    # the team is considered available.
    status = Column(bool, nullable=False, default=True)
    deapartment_id = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_latitude = Column(String(50), nullable=False)
    base_longitude = Column(String(50), nullable=False)
    coverage_radius_km = Column(Integer, nullable=False)

    # members = relationship(
    #     "Employee",
    #     secondary="team_members",
    #     back_populates="teams",
    #     cascade="all, delete",
    # )
    department = relationship(
        "Department", back_populates="teams", foreign_keys=[deapartment_id]
    )

    def __repr__(self):
        return f"<Team(team_id={self.team_id}, team_name='{self.team_name}', status='{self.status}')>"
