"""One-time Facebook login.

Opens a visible Chromium window pointed at facebook.com. You log in manually,
then close the window. The session cookies are saved to data/fb_session/ and
reused by the Facebook scraper on subsequent runs.

Usage:
    venv\\Scripts\\python.exe scripts\\facebook_login.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow the script to run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

from src.config import FB_SESSION_DIR


def main() -> int:
    FB_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Saving session to: {FB_SESSION_DIR}")
    print("A browser window will open. Log in to Facebook manually, then close the window.")
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(FB_SESSION_DIR),
            headless=False,
            viewport={"width": 1366, "height": 900},
            locale="fr-FR",
        )
        page = context.new_page()
        page.goto("https://www.facebook.com/login")
        # Wait for the user to close the browser window manually.
        try:
            page.wait_for_event("close", timeout=0)
        except KeyboardInterrupt:
            pass
        context.close()
    print("Session saved. You can now run the bot normally.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
