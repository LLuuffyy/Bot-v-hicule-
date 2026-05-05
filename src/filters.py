"""Filter and classify scraped listings against the user's hard requirements."""
from __future__ import annotations

import re
from typing import Iterable, Optional

from src.config import (
    CRITERIA,
    GLAZED_VAN_KEYWORDS,
    PANEL_VAN_KEYWORDS,
    RELIABLE_MODELS,
    UNRELIABLE_MODELS,
)
from src.models import Listing


def _norm(text: str) -> str:
    return text.lower() if text else ""


def detect_model(title: str, description: str = "") -> Optional[str]:
    """Return canonical model name if a known one is mentioned."""
    haystack = _norm(f"{title} {description}")
    for canonical, variants in {**RELIABLE_MODELS, **UNRELIABLE_MODELS}.items():
        if any(v in haystack for v in variants):
            return canonical
    return None


def classify_body(title: str, description: str = "") -> Optional[bool]:
    """Decide whether the ad describes a panel van (no rear windows).

    Returns True if confidently a panel van, False if confidently glazed,
    None when ambiguous (the listing will be flagged for manual verification).
    """
    haystack = _norm(f"{title} {description}")
    has_panel_keyword = any(k in haystack for k in PANEL_VAN_KEYWORDS)
    has_glazed_keyword = any(k in haystack for k in GLAZED_VAN_KEYWORDS)

    if has_glazed_keyword and not has_panel_keyword:
        return False
    if has_panel_keyword and not has_glazed_keyword:
        return True
    if has_panel_keyword and has_glazed_keyword:
        # Ambiguous wording: signal for manual review.
        return None
    # No keyword matched. Heuristic: titles mentioning "fourgon" without "vitré"
    # are likely panel vans; "ludospace" / "monospace" are family vans.
    if "fourgon" in haystack and "vitr" not in haystack:
        return True
    return None


_KM_RE = re.compile(r"(\d[\d\s]*)\s*(?:km|kms|kilom)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def parse_km(text: str) -> Optional[int]:
    if not text:
        return None
    m = _KM_RE.search(text)
    if not m:
        return None
    return int(m.group(1).replace(" ", ""))


def parse_year(text: str) -> Optional[int]:
    if not text:
        return None
    m = _YEAR_RE.search(text)
    if not m:
        return None
    year = int(m.group(0))
    return year if 1990 <= year <= 2030 else None


def passes_hard_filters(listing: Listing) -> tuple[bool, str]:
    """Check the user's non-negotiable criteria. Returns (ok, reason_if_rejected)."""
    if listing.price <= 0:
        return False, "no price"
    if listing.price < CRITERIA.min_price or listing.price > CRITERIA.max_price:
        return False, f"price {listing.price}€ out of {CRITERIA.min_price}-{CRITERIA.max_price}"
    if listing.year is not None and listing.year < CRITERIA.min_year:
        return False, f"year {listing.year} < {CRITERIA.min_year}"
    if listing.km is not None and listing.km > CRITERIA.max_km:
        return False, f"km {listing.km} > {CRITERIA.max_km}"
    if listing.distance_km is not None and listing.distance_km > CRITERIA.radius_km:
        return False, f"distance {listing.distance_km}km > {CRITERIA.radius_km}km"
    if listing.fuel and listing.fuel.lower() not in CRITERIA.fuel_types:
        return False, f"fuel {listing.fuel} not allowed"
    # Glazed van confirmed: hard reject. Ambiguous (None) is allowed through
    # so the user can verify themselves.
    if listing.is_panel_van is False:
        return False, "rear windows detected"
    if listing.has_valid_ct is False:
        return False, "no valid CT"
    return True, ""


def enrich(listing: Listing) -> Listing:
    """Fill in derived fields (model, panel-van classification, parsed km/year)."""
    if listing.model_canonical is None:
        listing.model_canonical = detect_model(listing.title, listing.description)
    if listing.is_panel_van is None:
        listing.is_panel_van = classify_body(listing.title, listing.description)
    if listing.km is None:
        listing.km = parse_km(listing.title) or parse_km(listing.description)
    if listing.year is None:
        listing.year = parse_year(listing.title) or parse_year(listing.description)
    return listing


def filter_listings(listings: Iterable[Listing]) -> tuple[list[Listing], list[tuple[Listing, str]]]:
    kept: list[Listing] = []
    rejected: list[tuple[Listing, str]] = []
    for listing in listings:
        enrich(listing)
        ok, reason = passes_hard_filters(listing)
        if ok:
            kept.append(listing)
        else:
            rejected.append((listing, reason))
    return kept, rejected
