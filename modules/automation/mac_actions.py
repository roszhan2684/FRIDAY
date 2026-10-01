"""macOS action executor — runs all tool calls against the operating system.

Uses:
  - subprocess + `open` for files, apps, URLs
  - subprocess + `osascript` for AppleScript automation
  - Spotlight via file_search module
  - No third-party dependencies for core actions
"""
from __future__ import annotations
import json
import logging
import subprocess
from pathlib import Path

from modules.automation.file_search import resolve_file, spotlight_search, register_alias
from modules.automation.chrome_profiles import open_url_in_chrome, open_urls_in_chrome, open_url_groups_in_chrome, resolve_profile
from modules.memory.command_registry import find_command, increment_use
from shared.schemas import ActionResult, ToolCall, Routine, RoutineStep
from database import db

logger = logging.getLogger(__name__)


class MacActionExecutor:

    def execute(self, tool_call: ToolCall) -> ActionResult:
        """Dispatch tool call to the appropriate handler."""
        handler = getattr(self, f"_tool_{tool_call.tool}", None)
        if handler is None:
            return ActionResult(success=False, error=f"Unknown tool: {tool_call.tool}")
        try:
            return handler(**tool_call.args)
        except TypeError as exc:
            return ActionResult(success=False, error=f"Bad args for {tool_call.tool}: {exc}")
        except Exception as exc:
            logger.exception("Tool execution error (%s): %s", tool_call.tool, exc)
            return ActionResult(success=False, error=str(exc))

    # ─── File Tools ───────────────────────────────────────────────────────────

    def _tool_open_file(self, query: str, hint: str = "") -> ActionResult:
        path = resolve_file(query, hint)
        if not path:
            return ActionResult(
                success=False,
                error=f"Could not find a file matching '{query}'.",
                metadata={"query": query},
            )
        result = subprocess.run(["open", path], capture_output=True, text=True)
        if result.returncode == 0:
            register_alias(query, path)
            db.execute(
                """INSERT INTO file_references(path, open_count, last_opened)
                   VALUES (?, 1, datetime('now'))
                   ON CONFLICT(path) DO UPDATE SET
                       open_count = open_count + 1,
                       last_opened = datetime('now')""",
                (path,),
            )
            return ActionResult(success=True, output=path, metadata={"path": path})
        return ActionResult(success=False, error=result.stderr)

    def _tool_reveal_in_finder(self, query: str) -> ActionResult:
        path = resolve_file(query)
        if not path:
            return ActionResult(success=False, error=f"No file found for '{query}'.")
        result = subprocess.run(["open", "-R", path], capture_output=True)
        return ActionResult(success=result.returncode == 0, output=path)

    def _tool_search_files(self, query: str, limit: int = 5) -> ActionResult:
        results = spotlight_search(query, limit=limit)
        return ActionResult(
            success=True,
            output=f"Found {len(results)} files",
            metadata={"results": results},
        )

    # ─── App Tools ────────────────────────────────────────────────────────────

    def _tool_open_app(self, name: str) -> ActionResult:
        result = subprocess.run(["open", "-a", name], capture_output=True, text=True)
        if result.returncode != 0:
            # Fallback: try spotlight for .app bundle
            apps = spotlight_search(f"{name}.app", limit=3)
            for app_path in apps:
                if app_path.endswith(".app"):
                    r2 = subprocess.run(["open", app_path], capture_output=True)
                    if r2.returncode == 0:
                        return ActionResult(success=True, output=app_path)
            return ActionResult(success=False, error=f"App '{name}' not found.")
        return ActionResult(success=True, output=f"Opened {name}")

    def _tool_switch_app(self, name: str) -> ActionResult:
        script = f'tell application "{name}" to activate'
        result = self._osascript(script)
        return ActionResult(success=result.returncode == 0, error=result.stderr or None)

    # ─── URL Tools ────────────────────────────────────────────────────────────

    def _tool_open_url(self, url: str) -> ActionResult:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        result = subprocess.run(["open", url], capture_output=True, text=True)
        return ActionResult(success=result.returncode == 0, output=url)

    # ─── Routine Tools ────────────────────────────────────────────────────────

    def _tool_run_routine(self, name: str) -> ActionResult:
        row = db.fetchone(
            "SELECT * FROM routines WHERE LOWER(name) = LOWER(?)", (name,)
        )
        if not row:
            return ActionResult(success=False, error=f"Routine '{name}' not found.")

        steps_data = json.loads(row["steps"])
        steps = [RoutineStep(**s) for s in steps_data]
        errors = []
        successes = 0

        for step in steps:
            if step.delay_seconds > 0:
                import time
                time.sleep(step.delay_seconds)
            fake_call = ToolCall(tool=step.tool, args=step.args, spoken_response="", confidence=1.0)
            result = self.execute(fake_call)
            if result.success:
                successes += 1
            else:
                errors.append(f"{step.tool}: {result.error}")
                logger.warning("Routine step failed (non-fatal): %s", result.error)

        db.execute(
            "UPDATE routines SET use_count = use_count + 1 WHERE LOWER(name) = LOWER(?)",
            (name,),
        )
        # Routine succeeds if ANY step succeeded — partial runs are acceptable
        return ActionResult(
            success=successes > 0,
            output=f"Routine '{name}' complete ({successes}/{len(steps)} steps)",
            error="; ".join(errors) if errors and successes == 0 else None,
        )

    def _tool_create_routine(
        self, name: str, steps: list[dict], trigger_phrases: list[str]
    ) -> ActionResult:
        import uuid
        routine_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO routines(id, name, trigger_phrases, steps) VALUES (?, ?, ?, ?)",
            (routine_id, name, json.dumps(trigger_phrases), json.dumps(steps)),
        )
        return ActionResult(success=True, output=f"Routine '{name}' saved.")

    # ─── Reminder management tools ───────────────────────────────────────────

    def _tool_snooze_reminder(self, text: str, minutes: int = 30) -> ActionResult:
        from modules.memory.reminder_engine import snooze_reminder
        row = db.fetchone(
            "SELECT id, text FROM reminders WHERE LOWER(text) LIKE ? AND status='pending' ORDER BY due_at LIMIT 1",
            (f"%{text.lower()}%",),
        )
        if not row:
            return ActionResult(success=False, error=f"No pending reminder matching '{text}'.")
        snooze_reminder(row["id"], minutes)
        return ActionResult(success=True, output=f"Snoozed '{row['text']}' for {minutes} minutes, Boss.")

    def _tool_complete_reminder(self, text: str) -> ActionResult:
        from modules.memory.reminder_engine import complete_reminder
        row = db.fetchone(
            "SELECT id, text FROM reminders WHERE LOWER(text) LIKE ? AND status IN ('pending','fired') ORDER BY due_at LIMIT 1",
            (f"%{text.lower()}%",),
        )
        if not row:
            return ActionResult(success=False, error=f"No reminder matching '{text}'.")
        complete_reminder(row["id"])
        return ActionResult(success=True, output=f"Done — '{row['text']}' marked complete, Boss.")

    def _tool_check_shopping_item(self, item: str) -> ActionResult:
        from modules.memory.reminder_engine import check_shopping_item
        row = db.fetchone(
            "SELECT id, item FROM shopping_items WHERE LOWER(item) LIKE ? AND checked=0",
            (f"%{item.lower()}%",),
        )
        if not row:
            return ActionResult(success=False, error=f"'{item}' not found on shopping list.")
        check_shopping_item(row["id"])
        return ActionResult(success=True, output=f"Checked off '{row['item']}', Boss.")

    def _tool_clear_shopping_list(self) -> ActionResult:
        from modules.memory.reminder_engine import clear_checked_items, get_shopping_list
        items = get_shopping_list()
        for i in items:
            check_shopping_item = db.execute
            db.execute("UPDATE shopping_items SET checked=1 WHERE id=?", (i["id"],))
        return ActionResult(success=True, output=f"Shopping list cleared, Boss.")

    # ─── Memory / Preference Tools ────────────────────────────────────────────

    def _tool_set_preference(self, key: str, value: str) -> ActionResult:
        db.execute(
            "INSERT INTO preferences(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
            (key, value),
        )
        return ActionResult(success=True, output=f"Preference '{key}' set to '{value}'.")

    def _tool_clear_memory(self, type: str = "all") -> ActionResult:
        if type in ("aliases", "all"):
            db.execute("DELETE FROM learned_aliases")
        if type in ("corrections", "all"):
            db.execute("DELETE FROM correction_logs")
        return ActionResult(success=True, output=f"Memory cleared: {type}")

    def _tool_show_history(self) -> ActionResult:
        rows = db.fetchall(
            "SELECT transcript, tool_called, timestamp FROM interaction_events ORDER BY timestamp DESC LIMIT 20"
        )
        history = [dict(r) for r in rows]
        return ActionResult(success=True, output=f"{len(history)} recent commands", metadata={"history": history})

    def _tool_search_youtube(self, query: str) -> ActionResult:
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        result = subprocess.run(["open", url], capture_output=True, text=True)
        return ActionResult(
            success=result.returncode == 0,
            output=f"Searched YouTube for: {query}",
            metadata={"url": url, "query": query},
        )

    def _tool_lookup_movie(self, title: str) -> ActionResult:
        import urllib.parse
        encoded = urllib.parse.quote_plus(title)
        # JustWatch shows all streaming platforms for a title
        url = f"https://www.justwatch.com/us/search?q={encoded}"
        result = subprocess.run(["open", url], capture_output=True, text=True)
        return ActionResult(
            success=result.returncode == 0,
            output=f"Looking up where to watch: {title}",
            metadata={"url": url, "title": title},
        )

    def _tool_search_web(self, query: str) -> ActionResult:
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
        result = subprocess.run(["open", url], capture_output=True, text=True)
        return ActionResult(
            success=result.returncode == 0,
            output=f"Searched web for: {query}",
            metadata={"url": url, "query": query},
        )

    # ─── Phase 6: Second Brain + Reflection + Job Copilot ────────────────────

    def _tool_capture_note(self, text: str, category: str = "general") -> ActionResult:
        from modules.automation.reflection import tool_capture_note
        return tool_capture_note(text, category)

    def _tool_show_notes(self, category: str = "") -> ActionResult:
        from modules.automation.reflection import tool_show_notes
        return tool_show_notes(category)

    def _tool_daily_reflection(self) -> ActionResult:
        from modules.automation.reflection import tool_daily_reflection
        return tool_daily_reflection()

    def _tool_open_job_sites(self) -> ActionResult:
        from modules.automation.job_copilot import open_job_sites
        return open_job_sites()

    def _tool_research_company(self, company: str) -> ActionResult:
        from modules.automation.job_copilot import research_company
        return research_company(company)

    # ─── Custom Command Registry ──────────────────────────────────────────────

    def _tool_run_custom_command(self, trigger: str) -> ActionResult:
        """Execute a user-defined command from the personal registry."""
        cmd = find_command(trigger)
        if not cmd:
            return ActionResult(success=False, error=f"No custom command found for: '{trigger}'")

        increment_use(cmd["id"])
        targets = cmd.get("targets", [])
        browser = cmd.get("browser", "default")
        profile = cmd.get("browser_profile_email") or cmd.get("browser_profile_dir") or None
        errors = []
        success_count = 0

        # Group URLs by window_group, then launch in separate windows
        from collections import defaultdict
        url_groups: dict[int, list[str]] = defaultdict(list)
        for t in targets:
            if t["target_type"] == "url":
                group = t.get("window_group", 1) or 1
                url_groups[group].append(t["target_value"])

        non_urls = [t for t in targets if t["target_type"] != "url"]

        if url_groups:
            if browser == "chrome":
                if len(url_groups) > 1:
                    opened = open_url_groups_in_chrome(dict(url_groups), profile)
                else:
                    urls = list(url_groups.values())[0]
                    opened = open_urls_in_chrome(urls, profile)
                success_count += opened
            else:
                for urls in url_groups.values():
                    for url in urls:
                        result = subprocess.run(["open", url], capture_output=True)
                        if result.returncode == 0:
                            success_count += 1
                        else:
                            errors.append(f"Failed to open {url}")

        for t in non_urls:
            import time
            time.sleep(t.get("delay_seconds", 0.5))
            if t["target_type"] == "app":
                r = self._tool_open_app(name=t["target_value"])
            elif t["target_type"] in ("file", "folder"):
                r = self._tool_open_file(query=t["target_value"])
            else:
                continue
            if r.success:
                success_count += 1
            else:
                errors.append(r.error or f"Failed: {t['target_value']}")

        return ActionResult(
            success=success_count > 0,
            output=f"Opened {success_count}/{len(targets)} targets",
            error="; ".join(errors) if errors and success_count == 0 else None,
            metadata={"command_id": cmd["id"], "trigger": trigger},
        )

    def _tool_open_url_chrome_profile(self, url: str, profile: str) -> ActionResult:
        """Open a URL in a specific Chrome profile."""
        ok = open_url_in_chrome(url, profile)
        return ActionResult(
            success=ok,
            output=url,
            metadata={"profile": profile},
        )

    # ─── Reminders ────────────────────────────────────────────────────────────

    def _tool_create_reminder(self, text: str) -> ActionResult:
        from modules.memory.reminder_engine import create_reminder_from_text
        result = create_reminder_from_text(text)
        due_str = result.get("due_str", "")
        confirmation = f"Got it, Boss. I'll remind you {due_str} to {result['task'].lower()}." if due_str else f"Saved, Boss. Reminder: {result['task']}."
        return ActionResult(
            success=True,
            output=confirmation,
            metadata=result,
        )

    def _tool_query_reminders(self, scope: str = "today") -> ActionResult:
        from modules.memory.reminder_engine import get_today_reminders, get_pending_reminders
        reminders = get_today_reminders() if scope == "today" else get_pending_reminders()
        if not reminders:
            msg = "No reminders for today, Boss." if scope == "today" else "No pending reminders, Boss."
            return ActionResult(success=True, output=msg, metadata={"reminders": []})
        parts = []
        for r in reminders[:5]:
            due_str = ""
            if r.get("due_at"):
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(r["due_at"])
                    due_str = dt.strftime(" at %-I:%M %p")
                except Exception:
                    pass
            parts.append(f"{r['text']}{due_str}")
        output = f"You have {len(reminders)} reminder{'s' if len(reminders)>1 else ''}: " + "; ".join(parts) + "."
        return ActionResult(success=True, output=output, metadata={"reminders": reminders})

    def _tool_add_shopping_item(self, item: str, store: str = "", quantity: str = "") -> ActionResult:
        from modules.memory.reminder_engine import add_shopping_item
        sid = add_shopping_item(item, store, quantity)
        store_str = f" at {store}" if store else ""
        qty_str = f" ({quantity})" if quantity else ""
        return ActionResult(
            success=True,
            output=f"Added {item}{qty_str}{store_str} to your shopping list, Boss.",
            metadata={"id": sid, "item": item},
        )

    def _tool_query_shopping_list(self, store: str = "") -> ActionResult:
        from modules.memory.reminder_engine import get_shopping_list
        items = get_shopping_list(store)
        if not items:
            return ActionResult(success=True, output="Your shopping list is empty, Boss.", metadata={"items": []})
        item_text = ", ".join(
            f"{i['item']}{' (' + i['quantity'] + ')' if i['quantity'] else ''}"
            for i in items[:10]
        )
        return ActionResult(success=True, output=f"{len(items)} item{'s' if len(items)>1 else ''}: {item_text}.", metadata={"items": items})

    # ─── Calendar ─────────────────────────────────────────────────────────────

    def _tool_query_schedule(self, question: str = "today") -> ActionResult:
        from modules.automation.calendar_reader import (
            get_today_events, get_next_event, format_events_naturally
        )
        q = question.lower()
        events = get_today_events()

        if any(w in q for w in ["next", "coming up", "upcoming"]):
            next_ev = get_next_event()
            if not next_ev:
                output = "Nothing left on your calendar today, Boss."
            else:
                from modules.automation.calendar_reader import _format_time
                t = _format_time(next_ev.get("start_time",""))
                output = f"Your next event is {next_ev['title']} at {t}, Boss."
        elif any(w in q for w in ["free", "busy", "available"]):
            if not events:
                output = "You're free all day today, Boss."
            else:
                from modules.automation.briefing import _minutes_until
                upcoming = [e for e in events if _minutes_until(e.get("start_time","")) > 0]
                if upcoming:
                    from modules.automation.calendar_reader import _format_time
                    t = _format_time(upcoming[0].get("start_time",""))
                    output = f"You're free until {t}, Boss."
                else:
                    output = "You're free for the rest of today, Boss."
        else:
            output = format_events_naturally(events, "today")

        return ActionResult(success=True, output=output, metadata={"events": events})

    def _tool_get_briefing(self, mode: str = "full") -> ActionResult:
        from modules.automation.briefing import compose_briefing
        briefing = compose_briefing(mode=mode)
        return ActionResult(success=True, output=briefing, metadata={"mode": mode})

    def _tool_respond_only(self, message: str) -> ActionResult:
        return ActionResult(success=True, output=message)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _osascript(self, script: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
        )
