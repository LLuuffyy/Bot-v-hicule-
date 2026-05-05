"""Estimate the fair market price of a listing.

Two strategies blended:
- A static reference table (Argus 2026 estimates) for cold-start.
- A dynamic median computed from previously scraped listings stored in the DB.
"""
from __future__ import annotations

import sqlite3
import statistics
from typing import Optional

from src.models import Listing
from src.storage import market_samples


# Static fallback table: median asking price (€) for the listed model
# at the listed year, normalised around 150 000 km.
# Sources: l'Argus + Caradisiac cote 2026 utilitaires d'occasion.
REFERENCE_TABLE: dict[str, dict[int, int]] = {
    "Renault Kangoo": {
        2012: 5500, 2013: 6000, 2014: 6800, 2015: 7500,
        2016: 8500, 2017: 9500, 2018: 10500,
    },
    "Citroën Berlingo": {
        2012: 5800, 2013: 6300, 2014: 7000, 2015: 7800,
        2016: 8800, 2017: 9800, 2018: 10800,
    },
    "Peugeot Partner": {
        2012: 5800, 2013: 6300, 2014: 7000, 2015: 7800,
        2016: 8800, 2017: 9800, 2018: 10800,
    },
    "Renault Trafic": {
        2012: 8000, 2013: 9000, 2014: 10500, 2015: 12000,
        2016: 13500, 2017: 15000, 2018: 16500,
    },
    "Ford Transit Connect": {
        2012: 5500, 2013: 6200, 2014: 7000, 2015: 8000,
        2016: 9000, 2017: 10000, 2018: 11000,
    },
    "Volkswagen Caddy": {
        2012: 7000, 2013: 7800, 2014: 8800, 2015: 9800,
        2016: 11000, 2017: 12500, 2018: 14000,
    },
    "Fiat Doblo": {
        2012: 4500, 2013: 5000, 2014: 5800, 2015: 6500,
        2016: 7300, 2017: 8200, 2018: 9000,
    },
    "Mercedes Citan": {
        2013: 6500, 2014: 7300, 2015: 8200, 2016: 9200,
        2017: 10500, 2018: 11800,
    },
    "Dacia Dokker": {
        2013: 5000, 2014: 5500, 2015: 6200, 2016: 7000,
        2017: 7800, 2018: 8800,
    },
}


def _km_adjustment(km: Optional[int]) -> float:
    """Linear adjustment around a 150k km baseline.

    +1% per 10k km below baseline, -1% per 10k km above (capped at +/-25%).
    """
    if km is None:
        return 1.0
    delta = (150_000 - km) / 10_000  # positive when fewer km than baseline
    factor = 1.0 + 0.01 * delta
    return max(0.75, min(1.25, factor))


def reference_price(model: Optional[str], year: Optional[int], km: Optional[int]) -> Optional[int]:
    if not model or year is None:
        return None
    table = REFERENCE_TABLE.get(model)
    if not table:
        return None
    # Pick the closest known year (clamped to the table range).
    years = sorted(table.keys())
    closest = min(years, key=lambda y: abs(y - year))
    base = table[closest]
    return int(base * _km_adjustment(km))


def estimate(conn: sqlite3.Connection, listing: Listing) -> Optional[int]:
    """Return the best price estimate for this listing.

    Prefers a dynamic median (>= 5 samples) over the static reference.
    """
    if listing.model_canonical and listing.year is not None:
        samples = market_samples(conn, listing.model_canonical, listing.year, listing.km)
        if len(samples) >= 5:
            return int(statistics.median(samples))
    return reference_price(listing.model_canonical, listing.year, listing.km)
