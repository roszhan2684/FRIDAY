"""Phase 6 — Daily Reflection and Second-Brain Capture.

  - Daily reflection: summarizes what FRIDAY did today + what's pending
  - Second-brain capture: saves quick notes, ideas, and todos to SQLite
  - End-of-day summary: spoken summary of the day's activity
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime, date

from database import db
from shared.schemas import ActionResult


# ─── Second Brain / Quick Capture ────────────────────────────────────────────

def capture_note(text: str, category: str = "general") -> str:
    """Save a quick note to the second brain."""
    note_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO second_brain(id, text, category, created_at) VALUES(?,?,?,datetime('now'))",
        (note_id, text, category),
    )
    return note_id


def get_notes(category: str = "", limit: int = 20) -> list[dict]:
    """Retrieve recent notes from the second brain."""
    if category:
        rows = db.fetchall(
            "SELECT * FROM second_brain WHERE LOWER(category)=LOWER(?) ORDER BY created_at DESC LIMIT ?",
            (category, limit),
        )
    else:
        rows = db.fetchall(
            "SELECT * FROM second_brain ORDER BY created_at DESC LIMIT ?", (limit,)
        )
    return [dict(r) for r in rows]


# ─── Daily Reflection ─────────────────────────────────────────────────────────

def compose_daily_reflection() -> str:
    """
    Compose a spoken end-of-day summary:
    - Commands run today
    - Reminders fired / pending
    - Shopping list items
    - Notes captured
    """
    today = date.today().isoformat()

    # Commands today
    cmd_rows = db.fetchall(
        """SELECT tool_called, COUNT(*) as c
           FROM interaction_events
           WHERE DATE(timestamp)=? AND outcome='success' AND tool_called IS NOT NULL
           GROUP BY tool_called ORDER BY c DESC LIMIT 5""",
        (today,),
    )
    total_commands = sum(r["c"] for r in cmd_rows)

    # Reminders status
    fired = db.fetchall(
        "SELECT text FROM reminders WHERE DATE(fired_at)=? AND status='fired'", (today,)
    )
    pending_reminders = db.fetchall(
        "SELECT text FROM reminders WHERE status='pending' ORDER BY due_at LIMIT 3"
    )

    # Shopping items
    shopping = db.fetchall("SELECT item FROM shopping_items WHERE checked=0 LIMIT 5")

    # Build reflection
    parts = [f"Here's your day summary, Boss."]

    if total_commands > 0:
        top_tool = cmd_rows[0]["tool_called"] if cmd_rows else ""
        parts.append(f"You ran {total_commands} commands today, mostly {top_tool}.")

    if fired:
        names = ", ".join(r["text"][:30] for r in fired[:2])
        parts.append(f"I fired {len(fired)} reminder{'s' if len(fired)>1 else ''}: {names}.")

    if pending_reminders:
        names = ", ".join(r["text"][:25] for r in pending_reminders[:2])
        parts.append(f"Still pending: {names}.")

    if shopping:
        items = ", ".join(r["item"] for r in shopping[:3])
        parts.append(f"Shopping list has {len(shopping)} item{'s' if len(shopping)>1 else ''}: {items}.")

    if len(parts) == 1:
        parts.append("Quiet day today. Nothing notable to report.")

    return " ".join(parts)


# ─── Tool executors (wired into mac_actions) ──────────────────────────────────

def tool_capture_note(text: str, category: str = "general") -> ActionResult:
    note_id = capture_note(text, category)
    return ActionResult(
        success=True,
        output=f"Noted, Boss: {text[:60]}",
        metadata={"id": note_id, "category": category},
    )


def tool_daily_reflection() -> ActionResult:
    reflection = compose_daily_reflection()
    return ActionResult(success=True, output=reflection, metadata={"date": date.today().isoformat()})


def tool_show_notes(category: str = "") -> ActionResult:
    notes = get_notes(category, limit=10)
    if not notes:
        return ActionResult(success=True, output="No notes yet, Boss.")
    summary = f"{len(notes)} note{'s' if len(notes)>1 else ''}: " + "; ".join(n["text"][:40] for n in notes[:3])
    return ActionResult(success=True, output=summary, metadata={"notes": notes})
