"""GitRepo model for GitHub trending repositories"""

from sqlalchemy import Column, BigInteger, String, Integer, Text, DateTime
from datetime import datetime
from app.config.database import Base


class GitRepo(Base):
    """
    GitRepo model for storing GitHub trending repositories

    Maps to git_repos table in Spring Boot backend
    """
    __tablename__ = "git_repos"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Repository details
    full_name = Column(String(500), nullable=False)  # e.g., "facebook/react"
    url = Column(String(1000), nullable=False, unique=True)
    description = Column(Text)

    # Repository metadata
    language = Column(String(100))
    stars = Column(Integer, default=0)
    forks = Column(Integer, default=0)
    stars_this_week = Column(Integer, default=0)

    # Korean summary (LLM generated)
    summary_ko_title = Column(String(500))
    summary_ko_body = Column(Text)
    category = Column(String(50))  # Technology category

    # Trending metrics
    score = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GitRepo {self.full_name} ({self.stars} stars)>"
