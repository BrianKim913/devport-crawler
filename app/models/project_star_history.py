"""Project star history model aligned to DevPort Port API contract."""

from sqlalchemy import BigInteger, Column, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.config.database import Base


class ProjectStarHistory(Base):
    """Historical star snapshots mapped to `project_star_history` table."""

    __tablename__ = "project_star_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(BigInteger, ForeignKey("projects.id"), nullable=False)
    date = Column(Date, nullable=False)
    stars = Column(Integer, nullable=False)

    project = relationship("Project", backref="star_history")

    __table_args__ = (
        UniqueConstraint("project_id", "date", name="uk_project_star_history"),
    )

    def __repr__(self):
        return f"<ProjectStarHistory {self.project_id}:{self.date}>"
