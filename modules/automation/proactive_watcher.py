"""Proactive watcher — Phase 4 upgraded version.

Improvements over Phase 3:
  - Quiet hours: configurable do-not-disturb window (default 10 PM – 8 AM)
  - Acceptance learning: tracks which proactive suggestions are accepted/rejected
  - Event prep: alerts before events with meeting links + attached actions
  - Anti-annoyance: won't re-alert same event within cooldown window
  - Configurable thresholds per alert type
"""
from __future__ import annotations
import asyncio
import json
import logging
import threading
import time
from datetime import datetime, time as dtime
from typing import Callable

from modules.memory.reminder_engine import get_due_reminders, fire_reminder
from modules.automation.briefing import compose_urgent_briefing
from database import db

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 60
MEETING_ALERT_COOLDOWN_SECONDS = 300  # Don't re-alert same meeting within 5 min


class ProactiveWatcher:
    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._speak_callback: Callable[[str], None] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._alerted_events: dict[str, float] = {}   # event_key → last_alert_time
        self._pending_proactive_id: int | None = None  # DB id of last shown suggestion

    def start(self, speak_callback: Callable[[str], None],
              loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._speak_callback = speak_callback
        self._loop = loop
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="proactive-watcher")
        self._thread.start()
        logger.info("Proactive watcher started (polling every %ds)", POLL_INTERVAL_SECONDS)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

    def record_acceptance(self, accepted: bool) -> None:
        """Called by pipeline when user accepts or rejects a proactive suggestion."""
        if self._pending_proactive_id:
            db.execute(
                "UPDATE proactive_log SET accepted=? WHERE id=?",
                (1 if accepted else 0, self._pending_proactive_id),
            )
            self._pending_proactive_id = None

    # ─── Main loop ────────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        while self._running:
            try:
                if not self._is_quiet_hours():
                    self._check_reminders()
                    self._check_meetings()
                    self._clean_alert_cache()
                else:
                    logger.debug("Quiet hours active — proactive watcher paused")
            except Exception as exc:
                logger.exception("Proactive watcher error: %s", exc)
            time.sleep(POLL_INTERVAL_SECONDS)

    # ─── Quiet Hours ──────────────────────────────────────────────────────────

    def _is_quiet_hours(self) -> bool:
        """Return True if current time is within the quiet hours window."""
        if not self._is_proactive_enabled():
            return True
        start_h = int(self._pref("quiet_hours_start", "22"))
        end_h = int(self._pref("quiet_hours_end", "8"))
        now_h = datetime.now().hour
        if start_h > end_h:  # overnight window (e.g. 22–8)
            return now_h >= start_h or now_h < end_h
        return start_h <= now_h < end_h

    # ─── Reminders ────────────────────────────────────────────────────────────

    def _check_reminders(self) -> None:
        due = get_due_reminders()
        for reminder in due:
            fire_reminder(reminder["id"])
            text = reminder.get("text", "")
            place = reminder.get("place", "")
            spoken = (f"Boss, it's time. You wanted to go to {place} — {text.lower()}."
                      if place else f"Boss, reminder: {text}.")

            follow_up = reminder.get("follow_up_action")
            proactive_id = self._log_proactive("reminder_fire", {"reminder_id": reminder["id"], "text": text})
            if follow_up:
                try:
                    action = json.loads(follow_up)
                    offer = action.get("offer", "")
                    if offer:
                        spoken += f" {offer}"
                        self._pending_proactive_id = proactive_id
                except Exception:
                    pass

            logger.info("Firing reminder: %s", text)
            self._speak(spoken)

    # ─── Meeting Alerts ───────────────────────────────────────────────────────

    def _check_meetings(self) -> None:
        threshold = int(self._pref("proactive_meeting_threshold_minutes", "10"))
        urgent = compose_urgent_briefing()
        if not urgent:
            return

        event_key = urgent[:60]
        last_alert = self._alerted_events.get(event_key, 0)
        now = time.monotonic()

        if now - last_alert < MEETING_ALERT_COOLDOWN_SECONDS:
            return  # Already alerted recently

        self._alerted_events[event_key] = now
        proactive_id = self._log_proactive("meeting_alert", {"message": urgent})
        self._pending_proactive_id = proactive_id
        logger.info("Meeting alert: %s", urgent[:60])
        self._speak(urgent)

    # ─── Acceptance learning ──────────────────────────────────────────────────

    def _log_proactive(self, type_: str, payload: dict) -> int | None:
        """Log to proactive_log and return the row id."""
        try:
            conn = db.get_connection()
            cur = conn.execute(
                "INSERT INTO proactive_log(type, payload) VALUES(?,?) RETURNING id",
                (type_, json.dumps(payload)),
            )
            row = cur.fetchone()
            conn.commit()
            conn.close()
            return row[0] if row else None
        except Exception:
            db.execute("INSERT INTO proactive_log(type, payload) VALUES(?,?)",
                       (type_, json.dumps(payload)))
            return None

    def get_acceptance_rate(self, type_: str | None = None) -> dict:
        """Return acceptance rate stats for proactive suggestions."""
        q = ("SELECT type, "
             "SUM(CASE WHEN accepted=1 THEN 1 ELSE 0 END) as accepted, "
             "SUM(CASE WHEN accepted=0 THEN 1 ELSE 0 END) as rejected, "
             "COUNT(*) as total "
             "FROM proactive_log WHERE accepted IS NOT NULL")
        params: tuple = ()
        if type_:
            q += " AND type=?"
            params = (type_,)
        q += " GROUP BY type"
        rows = db.fetchall(q, params)
        return {r["type"]: {"accepted": r["accepted"], "rejected": r["rejected"],
                             "total": r["total"],
                             "rate": round(r["accepted"] / r["total"], 2) if r["total"] > 0 else 0}
                for r in rows}

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _speak(self, text: str) -> None:
        if self._speak_callback:
            self._speak_callback(text)

    def _clean_alert_cache(self) -> None:
        now = time.monotonic()
        self._alerted_events = {k: v for k, v in self._alerted_events.items()
                                 if now - v < 3600}

    def _is_proactive_enabled(self) -> bool:
        row = db.fetchone("SELECT value FROM preferences WHERE key='proactive_enabled'")
        return row["value"].lower() == "true" if row else True

    def _pref(self, key: str, default: str = "") -> str:
        row = db.fetchone("SELECT value FROM preferences WHERE key=?", (key,))
        return row["value"] if row else default
