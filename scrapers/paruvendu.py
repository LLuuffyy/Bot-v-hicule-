"""ParuVendu scraper — HTTP only, friendly site."""
from __future__ import annotations

import logging
import re
from typing import Optional

from selectolax.parser import HTMLParser

from scrapers.base import BaseScraper, http_client
from scrapers._html_helpers import extract_int, extract_year, norm_fuel
from src.config import CRITERIA
from src.geo import distance_from_home
from src.models import Listing


log = logging.getLogger(__name__)


SEARCH_URL = (
    "https://www.paruvendu.fr/a/voiture-occasion/utilitaire"
    "?px2={max_price}&an1={min_year}&km2={max_km}"
    "&dpt={dept}&proxi={radius_km}&p={page}"
)


class ParuVenduScraper(BaseScraper):
    name = "paruvendu"

    def fetch(self) -> list[Listing]:
        listings: list[Listing] = []
        with http_client() as client:
            for page_num in range(1, self.max_pages + 1):
                url = SEARCH_URL.format(
                    max_price=CRITERIA.max_price,
                    min_year=CRITERIA.min_year,
                    max_km=CRITERIA.max_km,
                    dept=CRITERIA.postal_code[:2],
                    radius_km=CRITERIA.radius_km,
                    page=page_num,
                )
                try:
                    resp = client.get(url)
                    resp.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    log.warning("[%s] page %d: %s", self.name, page_num, exc)
                    break
                self.save_debug(page_num, resp.text)
                page_listings = self._parse(resp.text)
                if not page_listings:
                    break
                listings.extend(page_listings)
                self.sleep()
        return listings

    def _parse(self, html: str) -> list[Listing]:
        tree = HTMLParser(html)
        results: list[Listing] = []
        for article in tree.css("article, div.annonce, li.annonce"):
            link = article.css_first("a[href*='/'], a[href]")
            if not link:
                continue
            href = link.attributes.get("href") or ""
            if not href:
                continue
            url = href if href.startswith("http") else f"https://www.paruvendu.fr{href}"
            ad_id_match = re.search(r"-(\d+)\.htm|/(\d{6,})/", href)
            if not ad_id_match:
                continue
            ad_id = ad_id_match.group(1) or ad_id_match.group(2)
            title_node = article.css_first("h2, h3, .titre, .title")
            price_node = article.css_first(".prix, .price, [class*=Price]")
            if not title_node or not price_node:
                continue
            price = extract_int(price_node.text())
            if not price:
                continue
            km_text = article.css_first(".km, [class*=mileage], [class*=Mileage]")
            year_text = article.css_first(".annee, [class*=year], [class*=Year]")
            city_node = article.css_first(".ville, .city, [class*=location]")
            postal = _extract_postal(city_node.text() if city_node else "")
            results.append(Listing(
                site=self.name,
                ad_id=str(ad_id),
                url=url,
                title=title_node.text(strip=True),
                price=price,
                km=extract_int(km_text.text()) if km_text else None,
                year=extract_year(year_text.text()) if year_text else extract_year(title_node.text()),
                city=city_node.text(strip=True) if city_node else None,
                postal_code=postal,
                distance_km=distance_from_home(postal),
            ))
        return results


def _extract_postal(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"\b(\d{5})\b", text)
    return m.group(1) if m else None
