"""Bot orchestrator: scrape → enrich → filter → score → notify."""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Iterable

from scrapers import ALL_SCRAPERS
from src import notifier
from src.config import LOG_PATH, TOP_N_RESULTS
from src.filters import filter_listings
from src.models import Listing
from src.scorer import score
from src.storage import connect, mark_notified, upsert


def setup_logging(verbose: bool = False) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(), logging.FileHandler(LOG_PATH, encoding="utf-8")]
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def deduplicate(listings: Iterable[Listing]) -> list[Listing]:
    """Remove duplicates that point to the same URL across sites (aggregators)."""
    seen: dict[str, Listing] = {}
    for listing in listings:
        key = listing.url or f"{listing.site}:{listing.ad_id}"
        if key not in seen:
            seen[key] = listing
    return list(seen.values())


def run(dry_run: bool = False, only: list[str] | None = None) -> int:
    log = logging.getLogger("main")

    log.info("Starting scrape run (dry_run=%s, only=%s)", dry_run, only)
    raw: list[Listing] = []
    for cls in ALL_SCRAPERS:
        if only and cls.name not in only:
            continue
        scraper = cls()
        raw.extend(scraper.safe_fetch())
    log.info("Scrapers returned %d raw listings", len(raw))

    raw = deduplicate(raw)
    log.info("After dedup: %d listings", len(raw))

    kept, rejected = filter_listings(raw)
    log.info("After filters: %d kept, %d rejected", len(kept), len(rejected))
    for listing, reason in rejected[:20]:
        log.debug("rejected [%s/%s]: %s", listing.site, listing.ad_id, reason)

    new_or_updated: list[Listing] = []
    with connect() as conn:
        for listing in kept:
            is_new, previous_price = upsert(conn, listing)
            score(conn, listing, previous_price=previous_price)
            if is_new or previous_price is not None:
                new_or_updated.append(listing)

    new_or_updated.sort(key=lambda l: l.score, reverse=True)
    top = new_or_updated[:TOP_N_RESULTS]
    log.info("New/updated this run: %d (top score: %s)",
             len(new_or_updated), top[0].score if top else "n/a")

    if dry_run:
        for listing in top:
            print(f"  [{listing.score:>3}] {listing.price:>5}€ "
                  f"({listing.price_delta_pct or 0:+.0f}%) "
                  f"{listing.title[:80]} — {listing.url}")
        return 0

    if top:
        if notifier.send(top, total_new=len(new_or_updated)):
            with connect() as conn:
                mark_notified(conn, top)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot véhicule utilitaire")
    parser.add_argument("--dry-run", action="store_true", help="Don't send email, print results")
    parser.add_argument("--only", nargs="*", help="Only run these scrapers (by name)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    return run(dry_run=args.dry_run, only=args.only)


if __name__ == "__main__":
    sys.exit(main())
