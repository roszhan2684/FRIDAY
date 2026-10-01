"""macOS Calendar reader using osascript (AppleScript).

Reads events from the macOS Calendar app and caches them in SQLite.
No additional dependencies required — uses system AppleScript.

Also supports icalBuddy if installed (brew install ical-buddy) for faster reads.
"""
from __future__ import annotations
import json
import logging
import re
import subprocess
import uuid
from datetime import datetime, timedelta, date
from pathlib import Path

from database import db

logger = logging.getLogger(__name__)

ICAL_BUDDY = Path("/usr/local/bin/icalBuddy")


# ─── Calendar reading ─────────────────────────────────────────────────────────

def _read_via_icalbuddy(days: int = 1) -> list[dict]:
    """Use icalBuddy for structured calendar output (fastest method)."""
    if not ICAL_BUDDY.exists():
        return []

    try:
        end_date = (date.today() + timedelta(days=days)).strftime("%m/%d/%Y")
        result = subprocess.run(
            [str(ICAL_BUDDY),
             "-f", "-nc", "-npn", "-iep", "title,startDate,endDate,location,url",
             f"eventsFrom:today to:{end_date}"],
            capture_output=True, text=True, timeout=10
        )
        return _parse_icalbuddy_output(result.stdout)
    except Exception as exc:
        logger.debug("icalBuddy read failed: %s", exc)
        return []


def _parse_icalbuddy_output(output: str) -> list[dict]:
    events = []
    current: dict = {}
    for line in output.splitlines():
        line = line.strip()
        if not line:
            if current:
                events.append(current)
            current = {}
            continue

        if not line.startswith("-") and not line.startswith(" ") and current:
            events.append(current)
            current = {"title": line}
        elif line.startswith("- ") and not current:
            current = {"title": line[2:].strip()}
        else:
            if "date:" in line.lower():
                dt_str = re.search(r"\d{4}-\d{2}-\d{2}.*", line)
                if dt_str:
                    try:
                        dt = datetime.fromisoformat(dt_str.group()[:19])
                        if "start" in line.lower() or "date" in line.lower():
                            current.setdefault("start_time", dt.isoformat())
                        else:
                            current.setdefault("end_time", dt.isoformat())
                    except Exception:
                        pass
            elif "location:" in line.lower():
                current["location"] = line.split(":", 1)[1].strip()
            elif "url:" in line.lower():
                current["url"] = line.split(":", 1)[1].strip()

    if current:
        events.append(current)
    return [e for e in events if "title" in e]


def _read_via_osascript(days: int = 1) -> list[dict]:
    """Read calendar events via AppleScript — no extra deps required."""
    end_dt = (datetime.now() + timedelta(days=days)).replace(
        hour=23, minute=59, second=59
    )
    start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    script = f"""
set startDate to date "{start_dt.strftime('%A, %B %d, %Y at 12:00:00 AM')}"
set endDate to date "{end_dt.strftime('%A, %B %d, %Y at 11:59:59 PM')}"
set output to ""
tell application "Calendar"
    repeat with cal in calendars
        set calName to name of cal
        set evList to (every event of cal whose start date >= startDate and start date <= endDate)
        repeat with ev in evList
            set evTitle to summary of ev
            set evStart to start date of ev
            set evEnd to end date of ev
            set loc to ""
            try
                set loc to location of ev
            end try
            set output to output & evTitle & "|" & (evStart as string) & "|" & (evEnd as string) & "|" & loc & "|" & calName & "\n"
        end repeat
    end repeat
end tell
return output
"""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15
        )
        return _parse_osascript_output(result.stdout)
    except subprocess.TimeoutExpired:
        logger.warning("osascript calendar read timed out")
        return []
    except Exception as exc:
        logger.error("osascript calendar read failed: %s", exc)
        return []


def _parse_osascript_output(output: str) -> list[dict]:
    events = []
    for line in output.strip().splitlines():
        parts = line.strip().split("|")
        if len(parts) < 2:
            continue
        try:
            title = parts[0].strip()
            start_str = parts[1].strip() if len(parts) > 1 else ""
            end_str = parts[2].strip() if len(parts) > 2 else ""
            location = parts[3].strip() if len(parts) > 3 else ""
            calendar_name = parts[4].strip() if len(parts) > 4 else ""

            # Parse AppleScript date string: "Thursday, April 24, 2026 at 10:00:00 AM"
            start_dt = _parse_applescript_date(start_str)
            end_dt = _parse_applescript_date(end_str)

            events.append({
                "title": title,
                "start_time": start_dt.isoformat() if start_dt else start_str,
                "end_time": end_dt.isoformat() if end_dt else end_str,
                "location": location,
                "calendar_name": calendar_name,
                "url": "",
            })
        except Exception:
            continue
    return events


def _parse_applescript_date(s: str) -> datetime | None:
    for fmt in [
        "%A, %B %d, %Y at %I:%M:%S %p",
        "%A, %B %d, %Y at %I:%M %p",
        "%B %d, %Y at %I:%M:%S %p",
        "%Y-%m-%dT%H:%M:%S",
    ]:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def get_events(days: int = 1, use_cache: bool = True) -> list[dict]:
    """
    Get calendar events. Uses icalBuddy → osascript → cache fallback.
    """
    # Try fresh reads first
    events = _read_via_icalbuddy(days) or _read_via_osascript(days)

    if events:
        # Cache the events
        cache_time = datetime.now().isoformat()
        db.execute("DELETE FROM calendar_events_cache WHERE cached_at < datetime('now', '-4 hours')")
        for ev in events:
            db.execute(
                """INSERT OR REPLACE INTO calendar_events_cache
                   (id, title, start_time, end_time, calendar_name, location, url, cached_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid4()), ev.get("title",""),
                 ev.get("start_time",""), ev.get("end_time",""),
                 ev.get("calendar_name",""), ev.get("location",""),
                 ev.get("url",""), cache_time),
            )
        return events

    if use_cache:
        logger.debug("Calendar read failed — using cache")
        rows = db.fetchall(
            "SELECT * FROM calendar_events_cache WHERE start_time >= ? ORDER BY start_time",
            (datetime.now().replace(hour=0, minute=0, second=0).isoformat(),),
        )
        return [dict(r) for r in rows]

    return []


def get_today_events() -> list[dict]:
    return get_events(days=1)


def get_next_event() -> dict | None:
    events = get_today_events()
    now = datetime.now()
    future = [e for e in events if e.get("start_time", "") > now.isoformat()]
    return future[0] if future else None


def format_events_naturally(events: list[dict], context: str = "today") -> str:
    """Convert event list to a natural spoken summary."""
    if not events:
        return f"You don't have anything scheduled {context}, Boss."

    if len(events) == 1:
        ev = events[0]
        t = _format_time(ev.get("start_time", ""))
        return f"You have {ev['title']} at {t}{context and ' '+context}, Boss."

    parts = []
    for ev in events[:4]:
        t = _format_time(ev.get("start_time", ""))
        parts.append(f"{ev['title']} at {t}")

    if len(events) > 4:
        parts.append(f"and {len(events)-4} more")

    return f"You have {', '.join(parts[:-1])}, and {parts[-1]} {context}, Boss."


def _format_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%-I:%M %p").replace(":00 ", " ")
    except Exception:
        return iso_str
