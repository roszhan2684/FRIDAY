"""Chrome profile detection and profile-specific URL launching.

Reads Chrome's Preferences files to discover all profiles and their accounts.
Launches URLs using a specific profile so the right Google account is used.
"""
from __future__ import annotations
import json
import logging
import os
import subprocess
from pathlib import Path

from database import db

logger = logging.getLogger(__name__)

CHROME_DIR = Path.home() / "Library/Application Support/Google/Chrome"
CHROME_BIN = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
CHROME_CANARY_BIN = Path("/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary")


# ─── Profile Discovery ────────────────────────────────────────────────────────

def discover_profiles() -> list[dict]:
    """
    Scan Chrome's profile directories and return profile metadata.
    Results are cached in the chrome_profiles DB table.
    """
    if not CHROME_DIR.exists():
        logger.warning("Chrome not installed at expected path: %s", CHROME_DIR)
        return []

    profiles = []
    for entry in sorted(CHROME_DIR.iterdir()):
        if not entry.is_dir():
            continue
        prefs_path = entry / "Preferences"
        if not prefs_path.exists():
            continue
        try:
            prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
            profile_info = prefs.get("profile", {})
            account_info = prefs.get("account_info", [{}])

            name = profile_info.get("name", entry.name)
            email = ""
            if account_info:
                email = account_info[0].get("email", "")

            profile = {
                "profile_dir": entry.name,
                "display_name": name,
                "email": email,
            }
            profiles.append(profile)
            # Cache in DB
            db.execute(
                """INSERT INTO chrome_profiles(profile_dir, display_name, email, last_seen)
                   VALUES (?,?,?,datetime('now'))
                   ON CONFLICT(profile_dir) DO UPDATE SET
                       display_name=excluded.display_name,
                       email=excluded.email,
                       last_seen=datetime('now')""",
                (entry.name, name, email),
            )
        except Exception as exc:
            logger.debug("Could not read Chrome profile %s: %s", entry.name, exc)

    logger.info("Discovered %d Chrome profile(s)", len(profiles))
    return profiles


def get_cached_profiles() -> list[dict]:
    """Return profiles from DB cache (populated by discover_profiles)."""
    rows = db.fetchall(
        "SELECT profile_dir, display_name, email FROM chrome_profiles ORDER BY profile_dir"
    )
    return [dict(r) for r in rows]


def resolve_profile(identifier: str) -> str | None:
    """
    Map an email address or display name to a Chrome profile directory.
    Runs discovery if cache is empty.
    identifier: e.g. 'roszhan.2684@gmail.com' or 'Work' or 'Profile 3'
    Returns: profile_dir string like 'Profile 3', or None.
    """
    profiles = get_cached_profiles()
    if not profiles:
        profiles = discover_profiles()

    identifier_lower = identifier.lower().strip()

    for p in profiles:
        # Exact profile dir match
        if p["profile_dir"].lower() == identifier_lower:
            return p["profile_dir"]
        # Email match
        if p["email"].lower() == identifier_lower:
            return p["profile_dir"]
        # Display name match
        if p["display_name"].lower() == identifier_lower:
            return p["profile_dir"]

    # Partial email match (e.g. just username part)
    for p in profiles:
        if identifier_lower in p["email"].lower():
            return p["profile_dir"]

    return None


# ─── URL Launching ────────────────────────────────────────────────────────────

def _chrome_binary() -> Path | None:
    if CHROME_BIN.exists():
        return CHROME_BIN
    if CHROME_CANARY_BIN.exists():
        return CHROME_CANARY_BIN
    # Try finding via mdfind
    result = subprocess.run(
        ["mdfind", "kMDItemCFBundleIdentifier == 'com.google.Chrome'"],
        capture_output=True, text=True, timeout=3
    )
    for line in result.stdout.splitlines():
        bin_path = Path(line.strip()) / "Contents/MacOS/Google Chrome"
        if bin_path.exists():
            return bin_path
    return None


def open_url_in_chrome(url: str, profile_identifier: str | None = None) -> bool:
    """
    Open a URL in Chrome, optionally in a specific profile.
    profile_identifier: email, display name, or profile dir (e.g. 'Profile 3')
    Returns True on success.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    chrome = _chrome_binary()
    if not chrome:
        logger.warning("Chrome not found — falling back to default browser")
        subprocess.run(["open", url])
        return True

    args = [str(chrome)]

    if profile_identifier:
        profile_dir = resolve_profile(profile_identifier)
        if profile_dir:
            args.append(f"--profile-directory={profile_dir}")
            logger.info("Opening %s in Chrome profile %s (%s)", url, profile_dir, profile_identifier)
        else:
            logger.warning("Chrome profile %r not found — using default profile", profile_identifier)

    args.append(url)

    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as exc:
        logger.error("Chrome launch failed: %s", exc)
        return False


def open_urls_in_chrome(urls: list[str], profile_identifier: str | None = None) -> int:
    """
    Open multiple URLs as tabs in a single Chrome window.
    Returns number of URLs successfully opened.
    """
    chrome = _chrome_binary()
    if not chrome:
        for url in urls:
            open_url_in_chrome(url, profile_identifier)
        return len(urls)

    args = [str(chrome)]
    if profile_identifier:
        profile_dir = resolve_profile(profile_identifier)
        if profile_dir:
            args.append(f"--profile-directory={profile_dir}")

    args.extend(url if url.startswith("http") else f"https://{url}" for url in urls)

    try:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return len(urls)
    except Exception as exc:
        logger.error("Chrome multi-URL launch failed: %s", exc)
        return 0


def open_url_groups_in_chrome(
    groups: dict[int, list[str]],
    profile_identifier: str | None = None,
) -> int:
    """
    Open URL groups in separate Chrome windows.
    groups: {1: [url1, url2], 2: [url3, url4]}  →  2 separate windows
    Returns total URLs opened.
    """
    import time
    chrome = _chrome_binary()
    profile_dir = None
    if profile_identifier:
        profile_dir = resolve_profile(profile_identifier)

    total = 0
    for i, (group_id, urls) in enumerate(sorted(groups.items())):
        if not urls:
            continue

        args = [str(chrome)] if chrome else ["open", "-a", "Google Chrome"]
        if profile_dir:
            args.append(f"--profile-directory={profile_dir}")
        if i > 0:
            args.append("--new-window")
        args.extend(url if url.startswith("http") else f"https://{url}" for url in urls)

        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            total += len(urls)
            logger.info("Opened window group %d: %d URLs", group_id, len(urls))
            if i < len(groups) - 1:
                time.sleep(1.0)  # Give Chrome time to open first window
        except Exception as exc:
            logger.error("Chrome group launch failed: %s", exc)

    return total
