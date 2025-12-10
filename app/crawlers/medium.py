"""Medium crawler using Playwright to fetch RSS feeds"""

from typing import List
from datetime import datetime
import asyncio
import feedparser
from playwright.async_api import async_playwright
from app.crawlers.base import BaseCrawler, RawArticle
from app.config.settings import settings


class MediumCrawler(BaseCrawler):
    """Crawler for Medium articles using RSS feeds from popular publications"""

    # Medium RSS feed URL pattern - Using publication feeds (tag feeds are 404)
    RSS_URL_PATTERN = "https://medium.com/feed/{publication}"

    # Popular programming publications (verified to have valid RSS feeds)
    PUBLICATIONS = [
        "towards-data-science",
        "better-programming",
        "javascript-in-plain-english",
        "python-in-plain-english",
        "gitconnected",
        "codex",
        "aws-in-plain-english",
        "dev-genius",
        "stackademic",
        "the-startup"
    ]

    async def crawl(self) -> List[RawArticle]:
        """
        Fetch articles from Medium RSS feeds using Playwright

        Returns:
            List of RawArticle objects
        """
        self.log_start()
        articles = []
        seen_urls = set()

        try:
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(
                    headless=settings.PLAYWRIGHT_HEADLESS
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                for publication in self.PUBLICATIONS:
                    try:
                        url = self.RSS_URL_PATTERN.format(publication=publication)
                        self.logger.info(f"Fetching RSS feed: {url}")

                        # Navigate to RSS feed URL with error handling
                        try:
                            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        except Exception as nav_error:
                            self.logger.warning(f"Navigation error for {publication}: {nav_error}")
                            # Add delay and continue to next publication
                            await asyncio.sleep(self.delay)
                            continue

                        if response and response.status == 200:
                            # Get page content
                            content = await page.content()

                            # Parse RSS feed
                            feed = feedparser.parse(content)

                            if not feed.entries:
                                self.logger.warning(f"No entries found in feed for publication {publication}")
                                await asyncio.sleep(self.delay)
                                continue

                            for entry in feed.entries[:10]:  # Limit per publication
                                try:
                                    # Skip duplicates across publications
                                    if entry.link in seen_urls:
                                        continue

                                    article = self._parse_entry(entry, publication)
                                    if not self.should_skip(article):
                                        articles.append(article)
                                        seen_urls.add(entry.link)
                                except Exception as e:
                                    self.logger.warning(f"Failed to parse entry: {e}")
                                    continue

                            self.logger.info(f"Fetched {len([a for a in articles if publication in a.tags])} articles from publication {publication}")
                        else:
                            status = response.status if response else "No response"
                            self.logger.warning(f"Failed to fetch publication {publication}: HTTP {status}")

                        # Add delay between publications to be polite
                        await asyncio.sleep(self.delay)

                    except Exception as e:
                        self.logger.warning(f"Failed to fetch publication {publication}: {e}")
                        await asyncio.sleep(self.delay)
                        continue

                await browser.close()

        except Exception as e:
            self.log_error(e)

        self.log_end(len(articles))
        return articles

    def _parse_entry(self, entry, publication: str) -> RawArticle:
        """Parse RSS entry into RawArticle"""
        # Parse published date
        published_at = datetime(*entry.published_parsed[:6])

        # Extract categories/tags
        tags = [publication]
        if hasattr(entry, 'tags'):
            tags.extend([t.term for t in entry.tags])

        # Get content/summary
        content = ""
        if hasattr(entry, 'summary'):
            content = entry.summary
        elif hasattr(entry, 'content'):
            content = entry.content[0].value

        # Estimate read time from content length (rough approximation)
        words = len(content.split())
        read_time_minutes = max(1, words // 200)  # Assume 200 words/min

        return RawArticle(
            title_en=entry.title,
            url=entry.link,
            source="medium",
            published_at=published_at,
            tags=tags,
            content=content,
            read_time=f"{read_time_minutes} min read",
            raw_data=dict(entry)
        )

    def should_skip(self, article: RawArticle) -> bool:
        """
        Skip articles based on criteria

        Args:
            article: RawArticle to check

        Returns:
            True if article should be skipped
        """
        # Skip if too old (more than 30 days)
        days_old = (datetime.utcnow() - article.published_at).days
        if days_old > 30:
            return True

        # Check for paywalled content (basic check)
        if "member-only" in article.url.lower():
            return True

        return False
