"""AutoScout24 scraper — uses the public listing JSON embedded in the page."""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from scrapers.base import BaseScraper, http_client
from scrapers._html_helpers import norm_fuel
from src.config import CRITERIA
from src.geo import distance_from_home
from src.models import Listing


log = logging.getLogger(__name__)


SEARCH_URL = (
    "https://www.autoscout24.fr/lst"
    "?atype=C&body=4"  # body=4 = panel van
    "&priceto={max_price}&fregfrom={min_year}&kmto={max_km}"
    "&zip={postal}&zipr={radius_km}"
    "&sort=age&desc=1&page={page}"
)


class AutoScout24Scraper(BaseScraper):
    name = "autoscout24"

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
                self.save_debug(page_num, resp.text)
                page_listings = self._parse(resp.text)
                if not page_listings:
                    break
                listings.extend(page_listings)
                self.sleep()
        return listings

    def _parse(self, html: str) -> list[Listing]:
        # AutoScout24 embeds a JSON-LD ItemList describing each listing.
        results: list[Listing] = []
        for raw in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            html, flags=re.DOTALL,
        ):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            items = data.get("itemListElement") if isinstance(data, dict) else None
            if not items:
                continue
            for item in items:
                product = item.get("item") if isinstance(item, dict) else None
                if not product:
                    continue
                try:
                    results.append(self._product_to_listing(product))
                except Exception:  # noqa: BLE001
                    continue
        return results

    def _product_to_listing(self, product: dict) -> Listing:
        offers = product.get("offers") or {}
        url = product.get("url") or ""
        ad_id_match = re.search(r"/(\d{6,})", url)
        ad_id = ad_id_match.group(1) if ad_id_match else url
        price = int(float(offers.get("price") or 0))
        return Listing(
            site=self.name,
            ad_id=ad_id,
            url=url,
            title=product.get("name", ""),
            price=price,
            description=product.get("description") or "",
            year=int(product.get("vehicleModelDate")[:4]) if product.get("vehicleModelDate") else None,
            km=_parse_km(product.get("mileageFromOdometer")),
            fuel=norm_fuel(product.get("fuelType")),
            image_url=(product.get("image") or [None])[0] if isinstance(product.get("image"), list) else product.get("image"),
        )


def _parse_km(odometer) -> Optional[int]:
    if not odometer:
        return None
    if isinstance(odometer, dict):
        try:
            return int(float(odometer.get("value", 0)))
        except (TypeError, ValueError):
            return None
    try:
        return int(odometer)
    except (TypeError, ValueError):
        return None
