"""Wake-up briefing composer.

Composes a spoken morning/evening briefing from:
  - Current time + greeting
  - Weather (wttr.in)
  - Today's calendar events
  - Pending reminders
  - Shopping list count
  - Closing prompt

The briefing is configurable via preferences and adapts to time of day.
"""
from __future__ import annotations
import logging
from datetime import datetime

from modules.automation.calendar_reader import get_today_events, format_events_naturally
from modules.automation.weather import get_current_weather, format_weather_naturally
from modules.memory.reminder_engine import get_today_reminders, get_pending_reminders, get_shopping_list
from database import db

logger = logging.getLogger(__name__)


def _pref(key: str, default: str = "true") -> str:
    row = db.fetchone("SELECT value FROM preferences WHERE key=?", (key,))
    return row["value"] if row else default


def _greeting(hour: int) -> str:
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


def _format_reminder_spoken(reminder: dict) -> str:
    text = reminder.get("text", "")
    due = reminder.get("due_at")
    if due:
        try:
            dt = datetime.fromisoformat(due)
            time_str = dt.strftime("%-I:%M %p").replace(":00 ", " ")
            return f"a reminder at {time_str} to {text.lower()}"
        except Exception:
            pass
    return f"a reminder to {text.lower()}"


def compose_briefing(
    mode: str = "auto",
    include_weather: bool | None = None,
    include_calendar: bool | None = None,
    include_reminders: bool | None = None,
) -> str:
    """
    Compose a full spoken briefing string.
    mode: 'auto' (use prefs), 'full', 'short', 'silent'
    """
    if mode == "silent":
        return "Yes, Boss?"

    now = datetime.now()
    hour = now.hour
    parts: list[str] = []

    wake_mode = _pref("wake_mode", "acknowledgment")
    if mode == "auto" and wake_mode == "acknowledgment":
        return "Yes, Boss?"

    # Greeting
    if _pref("briefing_greeting") == "true":
        time_str = now.strftime("%-I:%M %p")
        parts.append(f"{_greeting(hour)}, Boss. It's {time_str}.")

    # Weather
    use_weather = (include_weather if include_weather is not None
                   else _pref("briefing_weather") == "true")
    if use_weather:
        weather = get_current_weather()
        if weather:
            parts.append(format_weather_naturally(weather) + ".")

    # Calendar
    use_cal = (include_calendar if include_calendar is not None
               else _pref("briefing_calendar") == "true")
    if use_cal:
        events = get_today_events()
        if events:
            # Check for urgent event (within 15 min)
            urgent = [e for e in events
                      if 0 < _minutes_until(e.get("start_time","")) <= 15]
            if urgent:
                ev = urgent[0]
                mins = _minutes_until(ev.get("start_time",""))
                parts.append(
                    f"Boss, you have {ev['title']} in {mins} minutes."
                )
            elif len(events) <= 2:
                for ev in events:
                    t = _format_event_time(ev.get("start_time",""))
                    parts.append(f"You have {ev['title']} at {t}.")
            else:
                summary = format_events_naturally(events, "today")
                parts.append(summary)
        else:
            if mode == "full":
                parts.append("You don't have anything scheduled today.")

    # Reminders
    use_rem = (include_reminders if include_reminders is not None
               else _pref("briefing_reminders") == "true")
    if use_rem:
        reminders = get_today_reminders()
        if reminders:
            if len(reminders) == 1:
                parts.append(f"And {_format_reminder_spoken(reminders[0])}.")
            else:
                r_parts = [_format_reminder_spoken(r) for r in reminders[:3]]
                parts.append(f"You have {', '.join(r_parts)}.")

    # Shopping list hint
    shopping = get_shopping_list()
    if shopping and len(shopping) > 0:
        parts.append(f"You have {len(shopping)} item{'s' if len(shopping)>1 else ''} on your shopping list.")

    # Closing
    if not parts:
        return "Yes, Boss? What can I help you with?"

    parts.append("What can I help you with?")
    return " ".join(parts)


def compose_urgent_briefing() -> str | None:
    """Check for urgent events/reminders and compose a proactive alert if needed."""
    threshold = int(_pref("proactive_meeting_threshold_minutes", "10"))
    events = get_today_events()

    for ev in events:
        mins = _minutes_until(ev.get("start_time", ""))
        if 0 < mins <= threshold:
            url_hint = ""
            if ev.get("url"):
                url_hint = " Would you like me to open the link?"
            return (
                f"Boss, you have {ev['title']} in {mins} minute{'s' if mins>1 else ''}."
                f"{url_hint}"
            )
    return None


def _minutes_until(iso_str: str) -> int:
    try:
        dt = datetime.fromisoformat(iso_str)
        delta = (dt - datetime.now()).total_seconds() / 60
        return int(delta)
    except Exception:
        return 999


def _format_event_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%-I:%M %p").replace(":00 ", " ")
    except Exception:
        return iso_str
