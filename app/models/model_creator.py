"""Model Creator entity matching DevPort API schema"""

from sqlalchemy import Column, BigInteger, String, DateTime
from datetime import datetime

from app.config.database import Base


class ModelCreator(Base):
    """
    Model Creator (LLM Provider/Organization)

    Data source: Artificial Analysis API - model_creator object
    """
    __tablename__ = "model_creators"

    id = Column(BigInteger, primary_key=True, index=True)

    # API identifier (UUID from API)
    external_id = Column(String(100), unique=True, nullable=True, index=True)  # "d874d370-74d3-4fa0-ba00-5272f92f946b"

    # Identifiers
    slug = Column(String(100), nullable=False, unique=True, index=True)  # "alibaba", "openai", "anthropic"
    name = Column(String(200), nullable=False, unique=True)  # "Alibaba", "OpenAI", "Anthropic"

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<ModelCreator {self.slug}: {self.name}>"
