"""Deduplication service to prevent duplicate articles"""

from typing import List, Set
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from app.models.article import Article
from app.crawlers.base import RawArticle
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class DeduplicatorService:
    """Service to detect and prevent duplicate articles"""

    def __init__(self, db: Session):
        self.db = db
        self.similarity_threshold = settings.TITLE_SIMILARITY_THRESHOLD

    def is_duplicate(self, article: RawArticle) -> bool:
        """
        Check if an article is a duplicate

        Only checks URL for exact matches. Title similarity removed to avoid
        false positives when multiple articles cover the same breaking news/releases.

        Args:
            article: RawArticle to check

        Returns:
            True if duplicate, False otherwise
        """
        # Check: Exact URL match only
        if self._url_exists(article.url):
            logger.debug(f"Duplicate URL found: {article.url}")
            return True

        # Title similarity check REMOVED - causes false positives for:
        # - Multiple articles about same release/news
        # - Different perspectives on same topic
        # - Similar tutorial titles but different content

        return False

    def _url_exists(self, url: str) -> bool:
        """Check if URL already exists in database"""
        existing = self.db.query(Article).filter(Article.url == url).first()
        return existing is not None

    def _similar_title_exists(self, title: str) -> bool:
        """
        Check if a similar title exists in database

        Uses fuzzy string matching to find similar titles

        Args:
            title: Title to check

        Returns:
            True if similar title exists
        """
        # Get recent articles (last 30 days) to check against
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        recent_articles = self.db.query(Article).filter(
            Article.created_at >= thirty_days_ago
        ).all()

        for existing in recent_articles:
            similarity = self._calculate_similarity(title, existing.title_en)
            if similarity >= self.similarity_threshold:
                logger.debug(
                    f"Similar title match ({similarity:.2f}): "
                    f"'{title[:50]}' ~ '{existing.title_en[:50]}'"
                )
                return True

        return False

    @staticmethod
    def _calculate_similarity(str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings

        Args:
            str1: First string
            str2: Second string

        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        # Normalize strings
        s1 = str1.lower().strip()
        s2 = str2.lower().strip()

        # Use SequenceMatcher for fuzzy matching
        return SequenceMatcher(None, s1, s2).ratio()

    def filter_duplicates(
        self,
        articles: List[RawArticle],
        check_db: bool = True
    ) -> List[RawArticle]:
        """
        Filter out duplicate articles from a list

        Only checks URLs for deduplication. Title similarity removed to prevent
        filtering out multiple articles about the same topic/release.

        Args:
            articles: List of RawArticles to filter
            check_db: Whether to check database for duplicates

        Returns:
            List of non-duplicate articles
        """
        unique_articles = []
        seen_urls = set()

        for article in articles:
            # Skip if URL already seen in this batch
            if article.url in seen_urls:
                logger.debug(f"Duplicate in batch (URL): {article.url}")
                continue

            # Title similarity check REMOVED from batch filtering
            # Reason: When major news breaks (e.g., React 19 release),
            # multiple different articles will have similar titles but different content

            # Check database if requested
            if check_db and self.is_duplicate(article):
                logger.debug(f"Duplicate in database: {article.url}")
                continue

            # Article is unique
            unique_articles.append(article)
            seen_urls.add(article.url)

        logger.info(
            f"Filtered {len(articles)} articles -> {len(unique_articles)} unique"
        )

        return unique_articles

    def mark_existing_duplicates(self) -> int:
        """
        Find and remove existing duplicate articles in database (URL-based only)

        This is a maintenance operation to clean up the database.
        Only removes exact URL duplicates, not title similarities.

        Returns:
            Number of duplicates found and removed
        """
        all_articles = self.db.query(Article).order_by(Article.created_at.desc()).all()

        seen_urls = set()
        duplicates_to_remove = []

        for article in all_articles:
            # Check URL only
            if article.url in seen_urls:
                duplicates_to_remove.append(article.id)
                continue

            # Title similarity check REMOVED - not reliable for deduplication
            # Different articles can have similar titles (especially for breaking news)

            # Mark URL as seen
            seen_urls.add(article.url)

        # Remove duplicates
        if duplicates_to_remove:
            self.db.query(Article).filter(
                Article.id.in_(duplicates_to_remove)
            ).delete(synchronize_session=False)
            self.db.commit()

        logger.info(f"Removed {len(duplicates_to_remove)} duplicate articles (URL-based)")
        return len(duplicates_to_remove)
