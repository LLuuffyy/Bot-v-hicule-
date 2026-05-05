"""Domain models shared across scrapers, filters, scorer and notifier."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Listing:
    """A single classified ad fetched from one of the supported sites."""

    site: str
    ad_id: str
    url: str
    title: str
    price: int
    description: str = ""
    year: Optional[int] = None
    km: Optional[int] = None
    fuel: Optional[str] = None
    model_canonical: Optional[str] = None
    seats: Optional[int] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    distance_km: Optional[int] = None
    image_url: Optional[str] = None
    seller_type: Optional[str] = None  # "particulier" / "pro"
    has_valid_ct: Optional[bool] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    # Populated by filters.classify_body() — None means "unknown / verify".
    is_panel_van: Optional[bool] = None
    # Populated by scorer.
    score: int = 0
    market_price: Optional[int] = None
    price_delta_pct: Optional[float] = None
    flags: list[str] = field(default_factory=list)

    def primary_key(self) -> tuple[str, str]:
        return (self.site, self.ad_id)
