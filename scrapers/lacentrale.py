"""La Centrale scraper.

La Centrale puts results behind Cloudflare. Strategy: Playwright (stealth)
plus their public JSON listing endpoint exposed on result pages.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from selectolax.parser import HTMLParser

from scrapers.base import BaseScraper
from scrapers._playwright_helpers import browser_context, humanlike_pause
from src.config import CRITERIA
from src.geo import distance_from_home
from src.models import Listing


log = logging.getLogger(__name__)


SEARCH_URL_TEMPLATE = (
    "https://www.lacentrale.fr/listing"
    "?makesModelsCommercialNames=&categories=UTILITAIRE"
    "&priceMax={max_price}&yearMin={min_year}&mileageMax={max_km}"
    "&regions=FR-PAC%2CFR-OCC"  # PACA + Occitanie cover the 100km radius
    "&page={page}"
)

PRELOADED_STATE_RE = re.compile(
    r'window\.__PRELOADED_STATE__\s*=\s*({.*?});\s*</script>',
    re.DOTALL,
)


class LaCentraleScraper(BaseScraper):
    name = "lacentrale"
    requires_browser = True

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        with browser_context(headless=True) as ctx:
            page = ctx.new_page()
            for page_num in range(1, self.max_pages + 1):
                url = SEARCH_URL_TEMPLATE.format(
                    max_price=CRITERIA.max_price,
                    min_year=CRITERIA.min_year,
                    max_km=CRITERIA.max_km,
                    page=page_num,
                )
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                except Exception as exc:  # noqa: BLE001
                    log.warning("[%s] page %d goto failed: %s", self.name, page_num, exc)
                    break
                humanlike_pause()
                html = page.content()
                page_listings = self._parse_state(html) or self._parse_dom(html)
                if not page_listings:
                    break
                listings.extend(page_listings)
                self.sleep()
        return listings

    def _parse_state(self, html: str) -> list[Listing]:
        match = PRELOADED_STATE_RE.search(html)
        if not match:
            return []
        try:
            state = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
        ads = (
            state.get("searchListing", {}).get("results", {}).get("hits", [])
        ) or []
        results: list[Listing] = []
        for ad in ads:
            try:
                results.append(self._to_listing(ad))
            except Exception:  # noqa: BLE001
                continue
        return results

    def _parse_dom(self, html: str) -> list[Listing]:
        # Fallback: scrape the rendered HTML if the JSON state is missing.
        tree = HTMLParser(html)
        results: list[Listing] = []
        for card in tree.css('a[href*="/auto-occasion-annonce-"]'):
            href = card.attributes.get("href") or ""
            if not href:
                continue
            url = f"https://www.lacentrale.fr{href}" if href.startswith("/") else href
            ad_id_match = re.search(r"-(\d+)\.html", href)
            if not ad_id_match:
                continue
            title_node = card.css_first(".searchCard__title, h2")
            price_node = card.css_first(".searchCard__price, [class*=Price]")
            if not title_node or not price_node:
                continue
            price_int = _extract_int(price_node.text())
            if price_int is None:
                continue
            results.append(Listing(
                site=self.name,
                ad_id=ad_id_match.group(1),
                url=url,
                title=title_node.text(strip=True),
                price=price_int,
            ))
        return results

    def _to_listing(self, ad: dict) -> Listing:
        postal = ad.get("zipCode") or ad.get("zipcode")
        return Listing(
            site=self.name,
            ad_id=str(ad.get("classifiedReferenceId") or ad.get("id") or ""),
            url=f"https://www.lacentrale.fr{ad.get('classifiedURL', '')}" if ad.get("classifiedURL", "").startswith("/") else ad.get("classifiedURL") or "",
            title=f"{ad.get('make', '')} {ad.get('model', '')} {ad.get('version', '')}".strip(),
            price=int(ad.get("price") or 0),
            description=ad.get("description") or "",
            year=int(ad.get("year")) if ad.get("year") else None,
            km=int(ad.get("mileage")) if ad.get("mileage") else None,
            fuel=_norm_fuel(ad.get("energy")),
            city=ad.get("city"),
            postal_code=postal,
            distance_km=distance_from_home(postal),
            image_url=(ad.get("photoURLs") or [None])[0],
            seller_type="pro" if (ad.get("sellerType") or "").lower() == "professional" else "particulier",
        )


def _extract_int(text: str) -> Optional[int]:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def _norm_fuel(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.lower()
    if "diesel" in v or "gazole" in v or v == "die":
        return "diesel"
    if "essence" in v or v == "ess":
        return "essence"
    return v
