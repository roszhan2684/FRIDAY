"""Reminder engine — create, query, fire, snooze, and complete reminders.

All reminders are stored locally in SQLite. The ProactiveWatcher thread
checks every 60 seconds and fires due reminders via the pipeline.
"""
from __future__ import annotations
import json
import re
import uuid
from datetime import datetime, timedelta, date

from database import db


# ─── Parsing ──────────────────────────────────────────────────────────────────

def parse_reminder_time(text: str, reference: datetime | None = None) -> datetime | None:
    """
    Extract a datetime from natural language like:
      "at 2 PM", "tonight", "tomorrow morning", "in 30 minutes",
      "Friday at 3", "2:30 PM", "before my meeting"
    Returns a datetime or None if unparseable.
    """
    now = reference or datetime.now()
    t = text.lower().strip()

    # "in X minutes/hours"
    m = re.search(r"in (\d+)\s*(minute|min|hour|hr)s?", t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = timedelta(minutes=n) if unit.startswith("m") else timedelta(hours=n)
        return now + delta

    # Specific time patterns: "at 2 PM", "at 14:30", "2:30 PM"
    m = re.search(r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        meridiem = m.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        elif not meridiem and hour < 7:
            hour += 12  # assume PM for ambiguous times like "2"
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target

    # Day references
    if "tonight" in t:
        return now.replace(hour=20, minute=0, second=0, microsecond=0)
    if "tomorrow morning" in t:
        return (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    if "tomorrow" in t:
        return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    if "this evening" in t or "this afternoon" in t:
        return now.replace(hour=17, minute=0, second=0, microsecond=0)
    if "morning" in t:
        return now.replace(hour=8, minute=0, second=0, microsecond=0)

    # Day of week
    days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    for i, day in enumerate(days):
        if day in t:
            days_ahead = (i - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            target = now + timedelta(days=days_ahead)
            return target.replace(hour=9, minute=0, second=0, microsecond=0)

    return None


def parse_reminder(text: str) -> dict:
    """
    Parse a natural language reminder request into structured fields.
    Input: "Remind me to go to Target at 2 PM to buy avocados"
    Output: {task, due_at, place, category, follow_up_action}
    """
    t = text.lower()
    result: dict = {
        "raw_input": text,
        "task": text,
        "due_at": None,
        "place": None,
        "category": "general",
        "follow_up_action": None,
    }

    # Strip preamble
    for prefix in [
        "remind me to", "remind me that i need to", "remind me that",
        "remind me", "note that i need to", "note that",
        "at .* remind me to", "tell me to",
    ]:
        text_clean = re.sub(f"^{prefix}\\s*", "", t).strip()
        if text_clean and len(text_clean) < len(t):
            t = text_clean
            break

    result["task"] = t.strip().capitalize()

    # Extract place
    place_match = re.search(r"\bto\s+([\w\s']+?)(?:\s+(?:to|at|and|for)\b|$)", t)
    location_match = re.search(r"\bat\s+([A-Za-z\s]+?)(?:\s+(?:at|to|for)\b|$)", t)
    for m in [place_match, location_match]:
        if m:
            candidate = m.group(1).strip()
            # Filter out time words
            if not re.search(r"\d|pm|am|tonight|tomorrow|morning", candidate):
                result["place"] = candidate.title()
                if candidate.lower() in ("target", "walmart", "costco", "trader joes",
                                          "whole foods", "cvs", "walgreens", "grocery"):
                    result["category"] = "errand"
                    result["follow_up_action"] = json.dumps({
                        "tool": "open_url",
                        "args": {"url": f"https://maps.apple.com/?q={candidate.replace(' ','+')}&dirflg=d"},
                        "offer": f"Would you like me to open Maps for {candidate.title()}, Boss?"
                    })
                break

    # Extract time
    due = parse_reminder_time(text)
    if due:
        result["due_at"] = due.isoformat()

    return result


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def create_reminder(
    text: str,
    due_at: str | None = None,
    place: str | None = None,
    category: str = "general",
    follow_up_action: str | None = None,
    raw_input: str | None = None,
) -> str:
    rid = str(uuid.uuid4())
    db.execute(
        """INSERT INTO reminders
           (id, text, raw_input, due_at, place, category, follow_up_action)
           VALUES (?,?,?,?,?,?,?)""",
        (rid, text, raw_input or text, due_at, place, category, follow_up_action),
    )
    return rid


def create_reminder_from_text(utterance: str) -> dict:
    """
    Full pipeline: parse natural language → create in DB → return summary.
    Deduplicates: won't create if identical (text, due_at) already pending.
    """
    parsed = parse_reminder(utterance)

    # Dedup guard — skip if this exact reminder already exists and is pending
    existing = db.fetchone(
        "SELECT id FROM reminders WHERE LOWER(text)=LOWER(?) AND (due_at=? OR (due_at IS NULL AND ? IS NULL)) AND status='pending'",
        (parsed["task"], parsed.get("due_at"), parsed.get("due_at")),
    )
    if existing:
        due_str = ""
        if parsed.get("due_at"):
            due_dt = datetime.fromisoformat(parsed["due_at"])
            due_str = due_dt.strftime("at %-I:%M %p")
        return {
            "id": existing["id"],
            "task": parsed["task"],
            "due_at": parsed.get("due_at"),
            "due_str": due_str,
            "place": parsed.get("place"),
            "category": parsed.get("category"),
            "duplicate": True,
        }

    rid = create_reminder(
        text=parsed["task"],
        due_at=parsed.get("due_at"),
        place=parsed.get("place"),
        category=parsed.get("category", "general"),
        follow_up_action=parsed.get("follow_up_action"),
        raw_input=utterance,
    )
    due_str = ""
    if parsed.get("due_at"):
        due_dt = datetime.fromisoformat(parsed["due_at"])
        due_str = due_dt.strftime("at %-I:%M %p")
    return {
        "id": rid,
        "task": parsed["task"],
        "due_at": parsed.get("due_at"),
        "due_str": due_str,
        "place": parsed.get("place"),
        "category": parsed.get("category"),
    }


def get_pending_reminders(include_fired: bool = False) -> list[dict]:
    statuses = "('pending','snoozed')" if not include_fired else "('pending','snoozed','fired')"
    rows = db.fetchall(
        f"SELECT * FROM reminders WHERE status IN {statuses} ORDER BY due_at ASC NULLS LAST"
    )
    return [dict(r) for r in rows]


def get_due_reminders() -> list[dict]:
    """Return reminders that are due now (within 60s window)."""
    now = datetime.now().isoformat()
    rows = db.fetchall(
        "SELECT * FROM reminders WHERE status='pending' AND due_at IS NOT NULL AND due_at <= ?",
        (now,),
    )
    return [dict(r) for r in rows]


def get_today_reminders() -> list[dict]:
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today_end = datetime.now().replace(hour=23, minute=59, second=59).isoformat()
    rows = db.fetchall(
        "SELECT * FROM reminders WHERE status='pending' AND due_at BETWEEN ? AND ? ORDER BY due_at",
        (today_start, today_end),
    )
    return [dict(r) for r in rows]


def fire_reminder(reminder_id: str) -> None:
    db.execute(
        "UPDATE reminders SET status='fired', fired_at=datetime('now') WHERE id=?",
        (reminder_id,),
    )


def snooze_reminder(reminder_id: str, minutes: int = 10) -> None:
    snoozed_until = (datetime.now() + timedelta(minutes=minutes)).isoformat()
    db.execute(
        "UPDATE reminders SET status='snoozed', snoozed_until=?, due_at=? WHERE id=?",
        (snoozed_until, snoozed_until, reminder_id),
    )


def complete_reminder(reminder_id: str) -> None:
    db.execute(
        "UPDATE reminders SET status='done', updated_at=datetime('now') WHERE id=?",
        (reminder_id,),
    )


def dismiss_reminder(reminder_id: str) -> None:
    db.execute(
        "UPDATE reminders SET status='dismissed', updated_at=datetime('now') WHERE id=?",
        (reminder_id,),
    )


# ─── Shopping List ────────────────────────────────────────────────────────────

def add_shopping_item(item: str, store: str = "", quantity: str = "") -> str:
    # Dedup: skip if unchecked item with same name already on list
    existing = db.fetchone(
        "SELECT id FROM shopping_items WHERE LOWER(item)=LOWER(?) AND checked=0",
        (item.strip(),),
    )
    if existing:
        return existing["id"]
    sid = str(uuid.uuid4())
    db.execute(
        "INSERT INTO shopping_items(id, item, store, quantity) VALUES (?,?,?,?)",
        (sid, item.strip(), store.strip(), quantity.strip()),
    )
    return sid


def get_shopping_list(store: str = "") -> list[dict]:
    if store:
        rows = db.fetchall(
            "SELECT * FROM shopping_items WHERE checked=0 AND LOWER(store) LIKE ? ORDER BY added_at",
            (f"%{store.lower()}%",),
        )
    else:
        rows = db.fetchall(
            "SELECT * FROM shopping_items WHERE checked=0 ORDER BY store, item"
        )
    return [dict(r) for r in rows]


def check_shopping_item(item_id: str) -> None:
    db.execute("UPDATE shopping_items SET checked=1 WHERE id=?", (item_id,))


def clear_checked_items() -> int:
    rows = db.fetchall("SELECT id FROM shopping_items WHERE checked=1")
    db.execute("DELETE FROM shopping_items WHERE checked=1")
    return len(rows)
