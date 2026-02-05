"""Application settings and configuration"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "DevPort Crawler"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/devportdb"

    # LLM API for summarization
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    LLM_PROVIDER: str = "openai"  # "openai", "anthropic", or "gemini"

    # GitHub API
    GITHUB_TOKEN: Optional[str] = None

    # Artificial Analysis API (for LLM rankings)
    ARTIFICIAL_ANALYSIS_API_KEY: Optional[str] = None

    # Crawling settings
    CRAWL_DELAY_SECONDS: int = 2
    MAX_CONCURRENT_REQUESTS: int = 5
    USER_AGENT: str = "DevPortCrawler/1.0 (+https://devport.kr)"

    # Playwright settings
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT: int = 30000  # milliseconds

    # Deduplication
    TITLE_SIMILARITY_THRESHOLD: float = 0.9

    # Scoring
    GITHUB_SOURCE_WEIGHT: float = 2.0
    BLOG_SOURCE_WEIGHT: float = 1.0
    TIME_DECAY_DAYS: int = 7

    # Scoring - Time Decay (Exponential Decay System)
    SCORE_PLATEAU_DAYS: int = 2  # Days before score decay starts (fresh content plateau)
    SCORE_HALF_LIFE_DAYS: float = 4.0  # Exponential decay rate (days for score to halve)
    SCORE_MAX_AGE_DAYS: int = 14  # Articles older than this get zero score (hard cutoff)

    # Filtering
    MIN_REACTIONS_DEVTO: int = 10
    MIN_REACTIONS_HASHNODE: int = 5
    MIN_UPVOTES_REDDIT: int = 100
    MIN_STARS_GITHUB: int = 50

    # Reddit API (optional OAuth; falls back to public if missing)
    REDDIT_CLIENT_ID: Optional[str] = None
    REDDIT_CLIENT_SECRET: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


settings = Settings()
