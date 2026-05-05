"""Send the daily digest email via Gmail SMTP."""
from __future__ import annotations

import argparse
import logging
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Sequence

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.config import (
    CRITERIA,
    GMAIL_APP_PASSWORD,
    GMAIL_USER,
    NOTIFY_EMAIL,
    TEMPLATES_DIR,
)
from src.models import Listing


log = logging.getLogger(__name__)


def render_email(listings: Sequence[Listing], total_new: int) -> tuple[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("email.html.j2")
    html = template.render(
        listings=listings,
        count=total_new,
        max_price=CRITERIA.max_price,
        min_year=CRITERIA.min_year,
        max_km=CRITERIA.max_km,
        radius_km=CRITERIA.radius_km,
        postal_code=CRITERIA.postal_code,
        generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
    )

    if listings:
        best = listings[0]
        if best.price_delta_pct is not None and best.price_delta_pct < 0:
            subject = f"[Bot Véhicule] {total_new} nouvelles - meilleur deal: {best.price_delta_pct}% vs marché"
        else:
            subject = f"[Bot Véhicule] {total_new} nouvelles - top score: {best.score}/100"
    else:
        subject = "[Bot Véhicule] Aucune nouvelle annonce"

    return subject, html


def send(listings: Sequence[Listing], total_new: int) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        log.error("GMAIL_USER / GMAIL_APP_PASSWORD missing in .env — skipping email.")
        return False
    if not listings and total_new == 0:
        log.info("No new listings to report — skipping email.")
        return False

    subject, html = render_email(listings, total_new)

    msg = MIMEMultipart("alternative")
    msg["From"] = GMAIL_USER
    msg["To"] = NOTIFY_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html", "utf-8"))

    password = GMAIL_APP_PASSWORD.replace(" ", "")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, password)
        server.sendmail(GMAIL_USER, [NOTIFY_EMAIL], msg.as_string())
    log.info("Email sent to %s with %d listings.", NOTIFY_EMAIL, len(listings))
    return True


def _test_email() -> int:
    logging.basicConfig(level=logging.INFO)
    sample = Listing(
        site="test",
        ad_id="0",
        url="https://example.com/ad/0",
        title="Renault Kangoo Express dCi 90 - Test",
        price=7500,
        description="Annonce de test envoyée par le bot.",
        year=2016,
        km=120_000,
        fuel="diesel",
        model_canonical="Renault Kangoo",
        city="Toulon",
        postal_code="83000",
        distance_km=25,
        seller_type="particulier",
        is_panel_van=True,
        score=82,
        market_price=8500,
        price_delta_pct=-11.8,
        flags=["✓ tôlé confirmé", "🏆 modèle fiable"],
    )
    ok = send([sample], total_new=1)
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Send a test email")
    args = parser.parse_args()
    if args.test:
        sys.exit(_test_email())
