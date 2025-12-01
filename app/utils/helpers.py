"""Utility helper functions"""

from datetime import datetime
from typing import Optional
import re


def sanitize_url(url: str) -> str:
    """
    Sanitize and normalize URL

    Args:
        url: URL to sanitize

    Returns:
        Sanitized URL
    """
    url = url.strip()

    # Ensure https
    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)

    return url


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to maximum length

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def clean_html(html_text: str) -> str:
    """
    Remove HTML tags from text

    Args:
        html_text: HTML text

    Returns:
        Cleaned text
    """
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', html_text)

    # Remove extra whitespace
    clean = re.sub(r'\s+', ' ', clean)

    return clean.strip()


def parse_read_time(text: str) -> Optional[str]:
    """
    Parse and normalize read time text

    Args:
        text: Read time text (e.g., "5 min read", "10 minutes")

    Returns:
        Normalized read time string or None
    """
    if not text:
        return None

    # Extract number
    match = re.search(r'(\d+)', text)
    if match:
        minutes = int(match.group(1))
        return f"{minutes} min read"

    return None


def is_valid_url(url: str) -> bool:
    """
    Check if URL is valid

    Args:
        url: URL to check

    Returns:
        True if valid
    """
    pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )

    return bool(pattern.match(url))


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime to string

    Args:
        dt: Datetime object
        format_str: Format string

    Returns:
        Formatted datetime string
    """
    return dt.strftime(format_str)


def calculate_percentage(value: float, total: float) -> float:
    """
    Calculate percentage

    Args:
        value: Value
        total: Total

    Returns:
        Percentage (0-100)
    """
    if total == 0:
        return 0.0

    return round((value / total) * 100, 2)
