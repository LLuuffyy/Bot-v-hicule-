"""Score listings 0-100. Higher = better deal.

Weights are calibrated so that a typical good deal lands in the 60-80 range,
exceptional finds reach 90+.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from src.config import RELIABLE_MODELS, UNRELIABLE_MODELS
from src.models import Listing
from src.market_price import estimate


def _price_score(price: int, market: Optional[int]) -> int:
    if market is None or market <= 0:
        return 0
    ratio = price / market
    if ratio <= 0.75:
        return 40
    if ratio <= 0.90:
        return 25
    if ratio <= 1.00:
        return 10
    return 0


def _model_score(model: Optional[str]) -> int:
    if model in RELIABLE_MODELS:
        return 15
    if model in UNRELIABLE_MODELS:
        return -10
    return 0


def _km_score(km: Optional[int]) -> int:
    if km is None:
        return 0
    if km < 100_000:
        return 12
    if km < 150_000:
        return 8
    return 0


def _year_score(year: Optional[int]) -> int:
    if year is None:
        return 0
    if year >= 2017:
        return 8
    if year >= 2015:
        return 5
    return 0


def _distance_score(distance_km: Optional[int]) -> int:
    if distance_km is None:
        return 0
    if distance_km <= 30:
        return 8
    if distance_km <= 50:
        return 5
    return 0


def _description_penalty(description: str) -> int:
    if not description or len(description) < 100:
        return -10
    return 0


def score(conn: sqlite3.Connection, listing: Listing, previous_price: Optional[int] = None) -> Listing:
    """Compute the score and attach flags. Mutates and returns the listing."""
    market = estimate(conn, listing)
    listing.market_price = market
    if market and market > 0:
        listing.price_delta_pct = round((listing.price - market) / market * 100, 1)

    raw = (
        _price_score(listing.price, market)
        + _model_score(listing.model_canonical)
        + _km_score(listing.km)
        + _year_score(listing.year)
        + _distance_score(listing.distance_km)
        + _description_penalty(listing.description)
    )

    flags: list[str] = []
    if listing.is_panel_van is True:
        flags.append("✓ tôlé confirmé")
    elif listing.is_panel_van is None:
        flags.append("⚠ vitres à vérifier")
    if listing.model_canonical in RELIABLE_MODELS:
        flags.append("🏆 modèle fiable")
    if previous_price is not None and previous_price > listing.price:
        drop_pct = round((previous_price - listing.price) / previous_price * 100, 1)
        flags.append(f"💰 baisse de prix (-{drop_pct}%)")
        raw += 10
    if listing.price_delta_pct is not None and listing.price_delta_pct <= -15:
        flags.append(f"🔥 {abs(listing.price_delta_pct)}% sous le marché")
    if listing.seller_type == "particulier":
        raw += 5

    listing.score = max(0, min(100, raw))
    listing.flags = flags
    return listing
