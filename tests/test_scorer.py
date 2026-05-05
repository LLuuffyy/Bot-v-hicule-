"""Tests for the scoring engine."""
import sqlite3

import pytest

from src.market_price import reference_price
from src.models import Listing
from src.scorer import score
from src.storage import SCHEMA


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    yield c
    c.close()


def _listing(**overrides) -> Listing:
    base = dict(
        site="test", ad_id="1", url="https://x",
        title="Renault Kangoo Express dCi 90 fourgon tôlé",
        description="Très bon état général, vendu avec contrôle technique OK et entretien à jour",
        price=7000, year=2016, km=120_000, fuel="diesel",
        model_canonical="Renault Kangoo", distance_km=20,
        is_panel_van=True, has_valid_ct=True, seller_type="particulier",
    )
    base.update(overrides)
    return Listing(**base)


def test_reference_price_known_model():
    assert reference_price("Renault Kangoo", 2016, 150_000) == 8500
    # Adjusted upward for low km.
    assert reference_price("Renault Kangoo", 2016, 100_000) > 8500
    # Adjusted downward for high km.
    assert reference_price("Renault Kangoo", 2016, 200_000) < 8500


def test_reference_price_unknown_model():
    assert reference_price("Foo Bar", 2016, 150_000) is None


def test_score_great_deal(conn):
    # Price well below the 2016 Kangoo reference (8500€).
    l = _listing(price=6000)
    score(conn, l)
    assert l.market_price == 8500 + int(8500 * 0.03)  # km adjustment
    assert l.score >= 70  # Great deal + reliable model + low km + close
    assert any("tôlé" in f for f in l.flags)
    assert any("fiable" in f for f in l.flags)


def test_score_average_deal(conn):
    l = _listing(price=8500)  # roughly at market
    score(conn, l)
    assert 20 <= l.score <= 60


def test_score_overpriced(conn):
    l = _listing(price=11000)
    score(conn, l)
    assert l.score < 50


def test_score_price_drop_bonus(conn):
    l = _listing(price=7000)
    score(conn, l, previous_price=8000)
    assert any("baisse de prix" in f for f in l.flags)


def test_score_unreliable_model_penalised(conn):
    reliable = _listing(model_canonical="Renault Kangoo")
    unreliable = _listing(model_canonical="Fiat Doblo")
    score(conn, reliable)
    score(conn, unreliable)
    assert reliable.score > unreliable.score


def test_score_flags_ambiguous_body(conn):
    l = _listing(is_panel_van=None)
    score(conn, l)
    assert any("vérifier" in f for f in l.flags)


def test_score_flags_great_deal(conn):
    # 30% under market should trigger the fire flag.
    l = _listing(price=6000)
    score(conn, l)
    assert any("sous le marché" in f for f in l.flags)
