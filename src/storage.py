"""SQLite persistence + dedup + price-drop detection."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator, Optional

from src.config import DB_PATH
from src.models import Listing


SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    site TEXT NOT NULL,
    ad_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    price INTEGER NOT NULL,
    description TEXT,
    year INTEGER,
    km INTEGER,
    fuel TEXT,
    model_canonical TEXT,
    seats INTEGER,
    city TEXT,
    postal_code TEXT,
    distance_km INTEGER,
    image_url TEXT,
    seller_type TEXT,
    has_valid_ct INTEGER,
    is_panel_van INTEGER,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    notified INTEGER DEFAULT 0,
    PRIMARY KEY (site, ad_id)
);

CREATE TABLE IF NOT EXISTS price_history (
    site TEXT NOT NULL,
    ad_id TEXT NOT NULL,
    price INTEGER NOT NULL,
    seen_at TEXT NOT NULL,
    PRIMARY KEY (site, ad_id, seen_at)
);

CREATE INDEX IF NOT EXISTS idx_listings_model ON listings(model_canonical);
CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(first_seen);
"""


def _bool_to_int(value: Optional[bool]) -> Optional[int]:
    return None if value is None else int(value)


def _int_to_bool(value: Optional[int]) -> Optional[bool]:
    return None if value is None else bool(value)


@contextmanager
def connect(db_path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert(conn: sqlite3.Connection, listing: Listing) -> tuple[bool, Optional[int]]:
    """Insert or update a listing.

    Returns (is_new, previous_price). previous_price is set if the price
    changed between this fetch and the last one stored for this ad.
    """
    now = datetime.utcnow().isoformat()
    row = conn.execute(
        "SELECT price FROM listings WHERE site = ? AND ad_id = ?",
        (listing.site, listing.ad_id),
    ).fetchone()

    is_new = row is None
    previous_price: Optional[int] = None

    if is_new:
        conn.execute(
            """
            INSERT INTO listings (
                site, ad_id, url, title, price, description, year, km, fuel,
                model_canonical, seats, city, postal_code, distance_km,
                image_url, seller_type, has_valid_ct, is_panel_van,
                first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing.site, listing.ad_id, listing.url, listing.title,
                listing.price, listing.description, listing.year, listing.km,
                listing.fuel, listing.model_canonical, listing.seats,
                listing.city, listing.postal_code, listing.distance_km,
                listing.image_url, listing.seller_type,
                _bool_to_int(listing.has_valid_ct),
                _bool_to_int(listing.is_panel_van),
                now, now,
            ),
        )
    else:
        previous_price = int(row["price"]) if row["price"] != listing.price else None
        conn.execute(
            """
            UPDATE listings
               SET price = ?, title = ?, description = ?, year = COALESCE(?, year),
                   km = COALESCE(?, km), fuel = COALESCE(?, fuel),
                   model_canonical = COALESCE(?, model_canonical),
                   seats = COALESCE(?, seats), city = COALESCE(?, city),
                   postal_code = COALESCE(?, postal_code),
                   distance_km = COALESCE(?, distance_km),
                   image_url = COALESCE(?, image_url),
                   seller_type = COALESCE(?, seller_type),
                   has_valid_ct = COALESCE(?, has_valid_ct),
                   is_panel_van = COALESCE(?, is_panel_van),
                   last_seen = ?
             WHERE site = ? AND ad_id = ?
            """,
            (
                listing.price, listing.title, listing.description, listing.year,
                listing.km, listing.fuel, listing.model_canonical, listing.seats,
                listing.city, listing.postal_code, listing.distance_km,
                listing.image_url, listing.seller_type,
                _bool_to_int(listing.has_valid_ct),
                _bool_to_int(listing.is_panel_van),
                now,
                listing.site, listing.ad_id,
            ),
        )

    conn.execute(
        "INSERT OR IGNORE INTO price_history (site, ad_id, price, seen_at) VALUES (?, ?, ?, ?)",
        (listing.site, listing.ad_id, listing.price, now),
    )
    return is_new, previous_price


def mark_notified(conn: sqlite3.Connection, listings: Iterable[Listing]) -> None:
    conn.executemany(
        "UPDATE listings SET notified = 1 WHERE site = ? AND ad_id = ?",
        [(l.site, l.ad_id) for l in listings],
    )


def market_samples(
    conn: sqlite3.Connection,
    model_canonical: str,
    year: Optional[int],
    km: Optional[int],
    days: int = 90,
) -> list[int]:
    """Return historical prices for similar listings (rolling window)."""
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    params: list = [model_canonical, since]
    sql = """
        SELECT price FROM listings
         WHERE model_canonical = ? AND first_seen >= ?
    """
    if year is not None:
        sql += " AND year BETWEEN ? AND ?"
        params.extend([year - 2, year + 2])
    if km is not None:
        sql += " AND km BETWEEN ? AND ?"
        params.extend([max(0, km - 50_000), km + 50_000])
    rows = conn.execute(sql, params).fetchall()
    return [int(r["price"]) for r in rows if r["price"]]
