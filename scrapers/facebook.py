"""Facebook Marketplace scraper.

Requires a one-time interactive login via `scripts/facebook_login.py` to
populate the persistent session in `data/fb_session/`. After that the
scraper logs in automatically using the stored cookies.

Anti-bot mitigation: rate-limit aggressively, mimic human scrolls.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from scrapers.base import BaseScraper
from scrapers._playwright_helpers import browser_context, humanlike_pause
from src.config import CRITERIA, FB_SESSION_DIR
from src.models import Listing


log = logging.getLogger(__name__)


SEARCH_URL = (
    "https://www.facebook.com/marketplace/category/vehicles"
    "?minPrice=0&maxPrice={max_price}&minYear={min_year}&maxMileage={max_km}"
    "&query=fourgon%20utilitaire&exact=false"
    "&radius={radius_km}&latitude=43.27&longitude=6.00"
)


class FacebookScraper(BaseScraper):
    name = "facebook"
    requires_browser = True
    requires_login = True

    def fetch(self) -> list[Listing]:
        if not FB_SESSION_DIR.exists() or not any(FB_SESSION_DIR.iterdir()):
            log.warning(
                "[%s] no FB session found — run scripts/facebook_login.py first.",
                self.name,
            )
            return []
        url = SEARCH_URL.format(
            max_price=CRITERIA.max_price,
            min_year=CRITERIA.min_year,
            max_km=CRITERIA.max_km,
            radius_km=CRITERIA.radius_km,
        )
        listings: list[Listing] = []
        with browser_context(user_data_dir=FB_SESSION_DIR, headless=True) as ctx:
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] goto failed: %s", self.name, exc)
                return []
            humanlike_pause(2, 4)
            # Detect if we landed on a login page — session expired.
            if "login" in page.url:
                log.warning("[%s] session expired — re-run scripts/facebook_login.py", self.name)
                return []

            # Scroll a few times to lazy-load more results.
            for _ in range(4):
                page.evaluate("window.scrollBy(0, document.body.scrollHeight);")
                humanlike_pause(2, 3.5)

            html = page.content()
            listings.extend(self._parse(html))
        return listings

    def _parse(self, html: str) -> list[Listing]:
        # FB Marketplace doesn't expose a clean JSON; we rely on hrefs containing
        # /marketplace/item/<id>/ and adjacent text nodes for title/price.
        results: list[Listing] = []
        item_re = re.compile(r'/marketplace/item/(\d+)/')
        seen_ids: set[str] = set()

        # Crude but effective: find anchors and walk back to find price/title.
        # Use a regex over the HTML rather than a full DOM parse for speed.
        anchor_blocks = re.findall(
            r'(<a[^>]+href="/marketplace/item/(\d+)/[^"]*"[^>]*>.{0,3000}?</a>)',
            html, flags=re.DOTALL,
        )
        for block, item_id in anchor_blocks:
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            text = re.sub(r"<[^>]+>", " ", block)
            text = re.sub(r"\s+", " ", text).strip()
            price_match = re.search(r"(\d[\d\s ]*)\s*€", text)
            if not price_match:
                continue
            price = int(re.sub(r"\D", "", price_match.group(1)))
            # Title heuristic: take the part after the price up to ~80 chars.
            after_price = text[price_match.end():].strip()[:120]
            title = after_price or text[:120]

            results.append(Listing(
                site=self.name,
                ad_id=item_id,
                url=f"https://www.facebook.com/marketplace/item/{item_id}/",
                title=title,
                price=price,
                description=text[:500],
            ))
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = FacebookScraper()
    items = scraper.safe_fetch()
    print(f"Got {len(items)} listings")
    for item in items[:5]:
        print(f"  - {item.price}€ - {item.title[:60]}")
