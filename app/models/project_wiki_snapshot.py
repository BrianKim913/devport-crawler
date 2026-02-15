"""Project wiki snapshot database model."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.config.database import Base


class ProjectWikiSnapshot(Base):
    """Persisted wiki snapshot with Core-6 sections and readiness metadata."""

    __tablename__ = "project_wiki_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_external_id = Column(String(255), nullable=False, unique=True, index=True)

    generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Core-6 section payloads (stored as JSON)
    what_section = Column(JSON, nullable=False)
    how_section = Column(JSON, nullable=False)
    architecture_section = Column(JSON, nullable=False)
    activity_section = Column(JSON, nullable=False)
    releases_section = Column(JSON, nullable=False)
    chat_section = Column(JSON, nullable=False)

    # Readiness gates
    is_data_ready = Column(Boolean, nullable=False, default=False, index=True)
    hidden_sections = Column(JSON, nullable=False)  # Array of section names to hide
    readiness_metadata = Column(JSON, nullable=False)  # Detailed readiness scoring

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
