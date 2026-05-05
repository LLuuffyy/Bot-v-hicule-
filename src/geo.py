"""Lightweight French postal-code → distance helper.

We only need a coarse estimate to filter out far-away ads. Approximate
lat/lon for the reference postal code (83210 Belgentier) is hardcoded;
target postal codes are mapped to lat/lon using the *first two digits*
(département centroid) which is precise enough for a 100 km filter.
"""
from __future__ import annotations

import math
from typing import Optional

from src.config import CRITERIA


# Centroid of each French département (degree, decimal). Source: INSEE.
DEPT_CENTROIDS: dict[str, tuple[float, float]] = {
    "01": (46.10, 5.35), "02": (49.55, 3.55), "03": (46.40, 3.20),
    "04": (44.10, 6.30), "05": (44.65, 6.40), "06": (43.93, 7.18),
    "07": (44.75, 4.42), "08": (49.55, 4.65), "09": (42.95, 1.55),
    "10": (48.30, 4.07), "11": (43.10, 2.40), "12": (44.30, 2.55),
    "13": (43.55, 5.10), "14": (49.10, -0.35), "15": (45.05, 2.65),
    "16": (45.70, 0.10), "17": (45.75, -0.65), "18": (47.05, 2.45),
    "19": (45.35, 1.85), "21": (47.40, 4.85), "22": (48.50, -2.95),
    "23": (46.05, 2.05), "24": (45.15, 0.75), "25": (47.20, 6.30),
    "26": (44.65, 5.10), "27": (49.10, 1.10), "28": (48.30, 1.40),
    "29": (48.20, -4.10), "30": (44.05, 4.30), "31": (43.45, 1.30),
    "32": (43.65, 0.55), "33": (44.85, -0.55), "34": (43.55, 3.40),
    "35": (48.10, -1.65), "36": (46.80, 1.55), "37": (47.30, 0.70),
    "38": (45.30, 5.70), "39": (46.65, 5.65), "40": (43.95, -0.75),
    "41": (47.60, 1.40), "42": (45.65, 4.30), "43": (45.10, 3.85),
    "44": (47.30, -1.65), "45": (47.95, 2.30), "46": (44.60, 1.65),
    "47": (44.30, 0.65), "48": (44.55, 3.50), "49": (47.40, -0.55),
    "50": (49.10, -1.30), "51": (49.05, 4.05), "52": (48.10, 5.15),
    "53": (48.05, -0.65), "54": (48.65, 6.20), "55": (49.00, 5.40),
    "56": (47.85, -2.85), "57": (49.05, 6.65), "58": (47.10, 3.55),
    "59": (50.50, 3.10), "60": (49.40, 2.45), "61": (48.55, 0.10),
    "62": (50.50, 2.40), "63": (45.75, 3.15), "64": (43.30, -0.75),
    "65": (43.05, 0.15), "66": (42.65, 2.65), "67": (48.65, 7.65),
    "68": (47.85, 7.30), "69": (45.75, 4.65), "70": (47.65, 6.10),
    "71": (46.65, 4.50), "72": (47.95, 0.20), "73": (45.50, 6.55),
    "74": (46.05, 6.40), "75": (48.85, 2.35), "76": (49.65, 1.05),
    "77": (48.65, 3.05), "78": (48.80, 1.85), "79": (46.50, -0.45),
    "80": (49.95, 2.30), "81": (43.85, 2.20), "82": (44.05, 1.40),
    "83": (43.45, 6.25), "84": (44.00, 5.15), "85": (46.65, -1.40),
    "86": (46.55, 0.45), "87": (45.85, 1.20), "88": (48.20, 6.45),
    "89": (47.85, 3.55), "90": (47.65, 6.85), "91": (48.55, 2.25),
    "92": (48.85, 2.25), "93": (48.95, 2.45), "94": (48.80, 2.45),
    "95": (49.10, 2.10),
}

REFERENCE_LAT, REFERENCE_LON = 43.27, 6.00  # 83210 Belgentier


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def distance_from_home(postal_code: Optional[str]) -> Optional[int]:
    """Return approximate km between home and the given postal code."""
    if not postal_code or len(postal_code) < 2:
        return None
    centroid = DEPT_CENTROIDS.get(postal_code[:2])
    if not centroid:
        return None
    return int(_haversine(REFERENCE_LAT, REFERENCE_LON, *centroid))


def in_search_radius(postal_code: Optional[str]) -> bool:
    d = distance_from_home(postal_code)
    if d is None:
        return True  # benefit of the doubt; hard filter applied later if value known
    return d <= CRITERIA.radius_km
