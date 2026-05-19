"""Common interface for all scrapers.

Each concrete scraper subclasses BaseScraper and implements `fetch()`.
The base class handles error reporting and logging so the orchestrator can
keep going if one site is down.
"""
from __future__ import annotations

import abc
import logging
import time
from typing import Iterator

import httpx

from src.config import MAX_PAGES_PER_SCRAPER, RATE_LIMIT_SECONDS
from src.models import Listing


log = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


class ScraperError(Exception):
    pass


class BaseScraper(abc.ABC):
    name: str = "base"
    requires_browser: bool = False  # True for sites that need Playwright
    requires_login: bool = False  # True for Facebook

    def __init__(self) -> None:
        self.rate_limit = RATE_LIMIT_SECONDS
        self.max_pages = MAX_PAGES_PER_SCRAPER

    @abc.abstractmethod
    def fetch(self) -> list[Listing]:
        """Fetch listings matching the configured criteria."""

    def safe_fetch(self) -> list[Listing]:
        """Wrap fetch() so a single broken site doesn't crash the run."""
        try:
            log.info("[%s] fetching...", self.name)
            results = self.fetch()
            log.info("[%s] %d listings fetched.", self.name, len(results))
            return results
        except Exception as exc:  # noqa: BLE001 — third-party sites can fail in many ways
            log.warning("[%s] failed: %s", self.name, exc)
            return []

    def sleep(self) -> None:
        time.sleep(self.rate_limit)


def http_client() -> httpx.Client:
    return httpx.Client(headers=DEFAULT_HEADERS, timeout=20.0, follow_redirects=True)


def paginate(start: int = 1) -> Iterator[int]:
    yield from range(start, start + MAX_PAGES_PER_SCRAPER)
