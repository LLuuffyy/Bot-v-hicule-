"""LeBonCoin scraper.

Strategy: Playwright (stealth) to defeat Datadome, then extract the
`__NEXT_DATA__` JSON blob embedded in the page — it contains the full
listing data and is more stable than the DOM.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from scrapers.base import BaseScraper
from scrapers._playwright_helpers import browser_context, humanlike_pause
from src.config import CRITERIA
from src.geo import distance_from_home
from src.models import Listing


log = logging.getLogger(__name__)


# LeBonCoin: category 5 = "Utilitaires" (commercial vehicles).
# Locations format: City_Postal__lat_lon_radius_meters_<unused>
SEARCH_URL_TEMPLATE = (
    "https://www.leboncoin.fr/recherche"
    "?category=5"
    "&locations=Belgentier_{postal}__43.27_6.00_{radius_m}_30000"
    "&price=min-{max_price}"
    "&page={page}"
)

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


class LeBonCoinScraper(BaseScraper):
    name = "leboncoin"
    requires_browser = True

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        with browser_context(headless=True) as ctx:
            page = ctx.new_page()
            for page_num in range(1, self.max_pages + 1):
                url = SEARCH_URL_TEMPLATE.format(
                    postal=CRITERIA.postal_code,
                    radius_m=CRITERIA.radius_km * 1000,
                    max_price=CRITERIA.max_price,
                    page=page_num,
                )
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                except Exception as exc:  # noqa: BLE001
                    log.warning("[%s] page %d goto failed: %s", self.name, page_num, exc)
                    break
                humanlike_pause()
                html = page.content()
                self.save_debug(page_num, html)
                page_listings = self._parse(html)
                if not page_listings:
                    break
                listings.extend(page_listings)
                self.sleep()
        return listings

    def _parse(self, html: str) -> list[Listing]:
        match = NEXT_DATA_RE.search(html)
        if not match:
            log.warning("[%s] no __NEXT_DATA__ block — anti-bot probably triggered.", self.name)
            return []
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
        ads = (
            data.get("props", {})
                .get("pageProps", {})
                .get("searchData", {})
                .get("ads", [])
        ) or []
        results: list[Listing] = []
        for ad in ads:
            try:
                results.append(self._to_listing(ad))
            except Exception as exc:  # noqa: BLE001
                log.debug("[%s] ad parse failed: %s", self.name, exc)
        return results

    def _to_listing(self, ad: dict) -> Listing:
        location = ad.get("location") or {}
        attrs = {a.get("key"): a.get("value") for a in ad.get("attributes", []) or []}
        images = (ad.get("images") or {}).get("urls") or []
        postal = location.get("zipcode")

        return Listing(
            site=self.name,
            ad_id=str(ad.get("list_id") or ad.get("id") or ""),
            url=ad.get("url") or f"https://www.leboncoin.fr/utilitaires/{ad.get('list_id')}",
            title=ad.get("subject") or "",
            price=int(ad.get("price", [0])[0] if isinstance(ad.get("price"), list) else ad.get("price", 0)),
            description=ad.get("body") or "",
            year=_int(attrs.get("regdate")),
            km=_int(attrs.get("mileage")),
            fuel=_norm_fuel(attrs.get("fuel")),
            seats=_int(attrs.get("seats")),
            city=location.get("city"),
            postal_code=postal,
            distance_km=distance_from_home(postal),
            image_url=images[0] if images else None,
            seller_type="pro" if (ad.get("owner") or {}).get("type") == "pro" else "particulier",
        )


def _int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).replace(" ", ""))
    except (TypeError, ValueError):
        return None


def _norm_fuel(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.lower()
    if "diesel" in v or "gazole" in v:
        return "diesel"
    if "essence" in v:
        return "essence"
    return v
