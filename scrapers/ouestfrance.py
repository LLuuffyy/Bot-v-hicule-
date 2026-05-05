"""Ouest-France Auto scraper."""
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
    "https://www.ouestfrance-auto.com/voiture-occasion/utilitaire"
    "?prix_max={max_price}&annee_min={min_year}&km_max={max_km}"
    "&dpt={dept}&page={page}"
)


class OuestFranceScraper(BaseScraper):
    name = "ouestfrance"

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        with http_client() as client:
            for page_num in range(1, self.max_pages + 1):
                url = SEARCH_URL.format(
                    max_price=CRITERIA.max_price,
                    min_year=CRITERIA.min_year,
                    max_km=CRITERIA.max_km,
                    dept=CRITERIA.postal_code[:2],
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
        for card in tree.css(".vehicleCard, .annonce-vehicule, article"):
            link = card.css_first("a[href*='/annonce-']") or card.css_first("a[href]")
            if not link:
                continue
            href = link.attributes.get("href") or ""
            url = href if href.startswith("http") else f"https://www.ouestfrance-auto.com{href}"
            ad_id_match = re.search(r"-(\d{5,})", href)
            if not ad_id_match:
                continue
            title = (card.css_first("h2, h3, .title") or link).text(strip=True)
            price_node = card.css_first(".price, .prix")
            price = extract_int(price_node.text()) if price_node else None
            if not price:
                continue
            km_node = card.css_first("[class*=km], [class*=Mileage]")
            year_node = card.css_first("[class*=year], [class*=annee]")
            postal_match = re.search(r"\b(\d{5})\b", card.text())
            postal = postal_match.group(1) if postal_match else None
            results.append(Listing(
                site=self.name,
                ad_id=ad_id_match.group(1),
                url=url,
                title=title,
                price=price,
                km=extract_int(km_node.text()) if km_node else None,
                year=extract_year(year_node.text()) if year_node else extract_year(title),
                postal_code=postal,
                distance_km=distance_from_home(postal),
            ))
        return results
