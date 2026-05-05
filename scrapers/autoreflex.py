"""AutoReflex scraper."""
from __future__ import annotations

import logging
import re

from selectolax.parser import HTMLParser

from scrapers.base import BaseScraper, http_client
from scrapers._html_helpers import extract_int, extract_year
from src.config import CRITERIA
from src.geo import distance_from_home
from src.models import Listing


log = logging.getLogger(__name__)


SEARCH_URL = (
    "https://www.autoreflex.com/voiture-occasion-utilitaire"
    "?prix_max={max_price}&annee_min={min_year}&km_max={max_km}"
    "&cp={postal}&distance={radius_km}&page={page}"
)


class AutoReflexScraper(BaseScraper):
    name = "autoreflex"

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        with http_client() as client:
            for page_num in range(1, self.max_pages + 1):
                url = SEARCH_URL.format(
                    max_price=CRITERIA.max_price,
                    min_year=CRITERIA.min_year,
                    max_km=CRITERIA.max_km,
                    postal=CRITERIA.postal_code,
                    radius_km=CRITERIA.radius_km,
                    page=page_num,
                )
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    log.warning("[%s] page %d: %s", self.name, page_num, exc)
                    break
                page_listings = self._parse(resp.text)
                if not page_listings:
                    break
                listings.extend(page_listings)
                self.sleep()
        return listings

    def _parse(self, html: str) -> list[Listing]:
        tree = HTMLParser(html)
        results: list[Listing] = []
        for card in tree.css(".vehicule, .annonce, article"):
            link = card.css_first("a[href]")
            if not link:
                continue
            href = link.attributes.get("href") or ""
            url = href if href.startswith("http") else f"https://www.autoreflex.com{href}"
            ad_id_match = re.search(r"-(\d{5,})", href)
            if not ad_id_match:
                continue
            title_node = card.css_first("h2, h3, .titre")
            price_node = card.css_first(".prix, .price")
            if not title_node or not price_node:
                continue
            price = extract_int(price_node.text())
            if not price:
                continue
            postal_match = re.search(r"\b(\d{5})\b", card.text())
            postal = postal_match.group(1) if postal_match else None
            results.append(Listing(
                site=self.name,
                ad_id=ad_id_match.group(1),
                url=url,
                title=title_node.text(strip=True),
                price=price,
                year=extract_year(title_node.text()),
                postal_code=postal,
                distance_km=distance_from_home(postal),
            ))
        return results
