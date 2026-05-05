"""Tiny helpers shared across the HTTP-only scrapers."""
from __future__ import annotations

import re
from typing import Optional


def extract_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def extract_year(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"\b(19|20)\d{2}\b", text)
    if not m:
        return None
    y = int(m.group(0))
    return y if 1990 <= y <= 2030 else None


def norm_fuel(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = value.lower()
    if "diesel" in v or "gazole" in v or "gasoil" in v:
        return "diesel"
    if "essence" in v or "petrol" in v:
        return "essence"
    return v.strip()
