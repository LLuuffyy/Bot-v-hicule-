"""Tests for filters and listing classification."""
from src.filters import (
    classify_body,
    detect_model,
    enrich,
    parse_km,
    parse_year,
    passes_hard_filters,
)
from src.models import Listing


# ---------- Body classification (panel van detection) ----------

def test_classify_body_panel_van_keywords():
    assert classify_body("Renault Kangoo Express dCi 90 fourgon tôlé") is True
    assert classify_body("Berlingo aveugle 2 places") is True
    assert classify_body("Citroën Berlingo Fourgon", "Sans vitres arrière") is True


def test_classify_body_glazed_keywords():
    assert classify_body("Renault Kangoo Family vitré 5 places") is False
    assert classify_body("Peugeot Partner Tepee 7 places") is False
    assert classify_body("Citroën Berlingo Multispace") is False


def test_classify_body_ambiguous():
    # No keywords either way → unknown.
    assert classify_body("Camionnette à vendre", "Bon état général") is None


def test_classify_body_fourgon_default():
    # "fourgon" without any glazed keyword should classify as panel van.
    assert classify_body("Fourgon Iveco Daily 2014") is True


# ---------- Model detection ----------

def test_detect_model_whitelist():
    assert detect_model("Renault Kangoo Express dCi 75") == "Renault Kangoo"
    assert detect_model("Citroën Berlingo Fourgon HDi") == "Citroën Berlingo"
    assert detect_model("Peugeot PARTNER 1.6 HDI") == "Peugeot Partner"
    assert detect_model("Volkswagen Caddy 1.6 TDI") == "Volkswagen Caddy"


def test_detect_model_blacklist():
    assert detect_model("Fiat Doblo Cargo Maxi") == "Fiat Doblo"
    assert detect_model("Mercedes Citan 109 CDI") == "Mercedes Citan"


def test_detect_model_unknown():
    assert detect_model("Iveco Daily 35S13") is None


# ---------- KM / year parsing ----------

def test_parse_km():
    assert parse_km("Vendu avec 145 000 km au compteur") == 145000
    assert parse_km("180000 kms") == 180000
    assert parse_km("Pas de kilométrage indiqué") is None


def test_parse_year():
    assert parse_year("Mise en circulation 2015") == 2015
    assert parse_year("Année 2018, état neuf") == 2018
    assert parse_year("Aucune année") is None


# ---------- Hard filters ----------

def _make_listing(**overrides) -> Listing:
    base = dict(
        site="test", ad_id="1", url="https://x", title="Renault Kangoo Express",
        price=7500, year=2015, km=120_000, fuel="diesel", distance_km=40,
        is_panel_van=True, has_valid_ct=True,
    )
    base.update(overrides)
    return Listing(**base)


def test_passes_hard_filters_happy_path():
    ok, reason = passes_hard_filters(_make_listing())
    assert ok, reason


def test_rejects_over_budget():
    ok, reason = passes_hard_filters(_make_listing(price=10000))
    assert not ok and "price" in reason


def test_rejects_too_old():
    ok, reason = passes_hard_filters(_make_listing(year=2008))
    assert not ok and "year" in reason


def test_rejects_too_many_km():
    ok, reason = passes_hard_filters(_make_listing(km=250_000))
    assert not ok and "km" in reason


def test_rejects_too_far():
    ok, reason = passes_hard_filters(_make_listing(distance_km=300))
    assert not ok and "distance" in reason


def test_rejects_glazed_van():
    ok, reason = passes_hard_filters(_make_listing(is_panel_van=False))
    assert not ok and "windows" in reason


def test_rejects_no_ct():
    ok, reason = passes_hard_filters(_make_listing(has_valid_ct=False))
    assert not ok and "CT" in reason


def test_allows_unknown_panel_van_status():
    # Ambiguous → kept (will be flagged in the email).
    ok, _ = passes_hard_filters(_make_listing(is_panel_van=None))
    assert ok


def test_rejects_disallowed_fuel():
    ok, reason = passes_hard_filters(_make_listing(fuel="électrique"))
    assert not ok and "fuel" in reason


# ---------- Enrich integration ----------

def test_enrich_fills_in_derived_fields():
    listing = Listing(
        site="test", ad_id="1", url="https://x",
        title="Renault Kangoo Express dCi 90 fourgon tôlé 2016",
        description="145 000 km, très bon état",
        price=7500,
    )
    enrich(listing)
    assert listing.model_canonical == "Renault Kangoo"
    assert listing.is_panel_van is True
    assert listing.year == 2016
    assert listing.km == 145000
