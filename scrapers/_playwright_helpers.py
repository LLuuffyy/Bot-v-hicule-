"""Shared Playwright helpers for the anti-bot-protected sites.

Importing playwright is wrapped so the module loads even when Playwright
is not yet installed (handy for unit tests on machines without browsers).
"""
from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


log = logging.getLogger(__name__)


@contextmanager
def browser_context(
    user_data_dir: Optional[Path] = None,
    headless: bool = True,
) -> Iterator:
    """Yield a Playwright BrowserContext with stealth tweaks applied.

    Pass `user_data_dir` for a persistent profile (Facebook session).
    Otherwise an ephemeral context is used.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed. Run: pip install playwright && playwright install chromium"
        ) from exc

    try:
        from playwright_stealth import stealth_sync
    except ImportError:
        stealth_sync = None  # type: ignore[assignment]

    with sync_playwright() as pw:
        if user_data_dir is not None:
            user_data_dir.mkdir(parents=True, exist_ok=True)
            context = pw.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=headless,
                viewport={"width": 1366, "height": 900},
                locale="fr-FR",
                timezone_id="Europe/Paris",
            )
        else:
            browser = pw.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={"width": 1366, "height": 900},
                locale="fr-FR",
                timezone_id="Europe/Paris",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
            )
        if stealth_sync is not None:
            try:
                page = context.new_page()
                stealth_sync(page)
                page.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            yield context
        finally:
            context.close()


def humanlike_pause(min_s: float = 1.5, max_s: float = 3.5) -> None:
    time.sleep(random.uniform(min_s, max_s))
