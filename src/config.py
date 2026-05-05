"""Central configuration for the bot.

Search criteria, brand whitelist/blacklist, keyword sets and tunable
thresholds all live here so they can be adjusted without touching the rest of
the code base.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = ROOT / "templates"
DB_PATH = DATA_DIR / "listings.db"
LOG_PATH = DATA_DIR / "runs.log"
FB_SESSION_DIR = DATA_DIR / "fb_session"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw and raw.strip() else default


@dataclass(frozen=True)
class SearchCriteria:
    postal_code: str = os.getenv("POSTAL_CODE", "83210")
    radius_km: int = _int_env("RADIUS_KM", 100)
    min_price: int = _int_env("MIN_PRICE", 0)
    max_price: int = _int_env("MAX_PRICE", 9000)
    min_year: int = _int_env("MIN_YEAR", 2012)
    max_km: int = _int_env("MAX_KM", 200_000)
    # Diesel preferred for pro use, but petrol still accepted.
    fuel_types: tuple[str, ...] = ("diesel", "essence")


CRITERIA = SearchCriteria()

# Whitelist: reliable utility vans known to be cheap to maintain.
# Each entry maps a canonical model name to keyword variants used to match
# scraped titles/descriptions.
RELIABLE_MODELS: dict[str, tuple[str, ...]] = {
    "Renault Kangoo": ("kangoo",),
    "Citroën Berlingo": ("berlingo",),
    "Peugeot Partner": ("partner",),
    "Renault Trafic": ("trafic", "traffic"),
    "Ford Transit Connect": ("transit connect", "tourneo connect"),
    "Volkswagen Caddy": ("caddy",),
}

# Blacklist: not excluded but penalised in scoring.
UNRELIABLE_MODELS: dict[str, tuple[str, ...]] = {
    "Fiat Doblo": ("doblo",),
    "Mercedes Citan": ("citan",),
    "Dacia Dokker": ("dokker",),
}

# Words that strongly indicate a panel van (no rear windows).
PANEL_VAN_KEYWORDS: tuple[str, ...] = (
    "tôlé",
    "tôlée",
    "tole",
    "tolee",
    "fourgon tôlé",
    "fourgon tole",
    "sans vitres",
    "sans vitre",
    "aveugle",
    "kangoo express",
    "express",
    "partner fourgon",
    "berlingo fourgon",
)

# Words that strongly indicate the vehicle has rear windows (excluded).
# We deliberately keep only the participial forms ("vitré", "vitrée") and
# avoid "vitre" alone — that bare noun also appears in panel-van phrases
# like "sans vitres arrière" and would create false positives.
GLAZED_VAN_KEYWORDS: tuple[str, ...] = (
    "vitré",
    "vitrée",
    "combi",
    "multispace",
    "tepee",
    "rifter",
    "kangoo family",
    "kangoo grand confort",
    "ludospace",
    "monospace",
    "passenger",
    "5 places",
    "7 places",
)

# Email / SMTP.
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", GMAIL_USER)

# Per-site rate limit (seconds between page requests).
RATE_LIMIT_SECONDS = 5
# Maximum result pages to fetch per scraper per run.
MAX_PAGES_PER_SCRAPER = 5
# How many top listings to include in the email.
TOP_N_RESULTS = 10
