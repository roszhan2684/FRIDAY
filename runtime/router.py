"""Additional HTTP route handlers for memory, settings, routines, and custom commands.

Mounted at /memory, /routines, /settings, /commands in main.py.
"""
from __future__ import annotations
import json
from fastapi import APIRouter

from modules.memory.store import (
    get_all_aliases,
    get_all_preferences,
    set_preference,
    list_routines,
    get_unexported_corrections,
)
from modules.memory.command_registry import (
    list_commands, find_command, save_command, delete_command,
)
from modules.automation.chrome_profiles import (
    discover_profiles, get_cached_profiles,
)
from modules.memory.learner import Learner
from database import db

memory_router = APIRouter(prefix="/memory", tags=["memory"])
routines_router = APIRouter(prefix="/routines", tags=["routines"])
settings_router = APIRouter(prefix="/settings", tags=["settings"])
commands_router = APIRouter(prefix="/commands", tags=["commands"])


# ─── Memory ───────────────────────────────────────────────────────────────────

@memory_router.get("/aliases")
async def get_aliases():
    return {"aliases": get_all_aliases()}


@memory_router.delete("/aliases/{phrase}")
async def delete_alias(phrase: str):
    db.execute("DELETE FROM learned_aliases WHERE LOWER(phrase) = LOWER(?)", (phrase,))
    return {"deleted": phrase}


@memory_router.get("/history")
async def get_history(limit: int = 50):
    rows = db.fetchall(
        "SELECT id, transcript, tool_called, outcome, timestamp FROM interaction_events ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    )
    return {"history": [dict(r) for r in rows]}


@memory_router.get("/corrections")
async def get_corrections():
    return {"corrections": get_unexported_corrections(limit=100)}


@memory_router.delete("/all")
async def clear_all_memory():
    db.execute("DELETE FROM learned_aliases")
    db.execute("DELETE FROM correction_logs")
    return {"cleared": True}


@memory_router.get("/suggestions")
async def get_suggestions():
    rows = db.fetchall(
        "SELECT id, name, steps, trigger_count, created_at FROM routine_suggestions WHERE accepted IS NULL ORDER BY trigger_count DESC"
    )
    return {"suggestions": [dict(r) for r in rows]}


@memory_router.post("/suggestions/{suggestion_id}/accept")
async def accept_suggestion(suggestion_id: str):
    db.execute("UPDATE routine_suggestions SET accepted = 1 WHERE id = ?", (suggestion_id,))
    return {"accepted": suggestion_id}


@memory_router.post("/suggestions/{suggestion_id}/reject")
async def reject_suggestion(suggestion_id: str):
    db.execute("UPDATE routine_suggestions SET accepted = 0 WHERE id = ?", (suggestion_id,))
    return {"rejected": suggestion_id}


# ─── Routines ─────────────────────────────────────────────────────────────────

@routines_router.get("/")
async def list_all_routines():
    return {"routines": list_routines()}


@routines_router.get("/{name}")
async def get_routine(name: str):
    row = db.fetchone("SELECT * FROM routines WHERE LOWER(name) = LOWER(?)", (name,))
    if not row:
        return {"error": f"Routine '{name}' not found"}
    d = dict(row)
    d["trigger_phrases"] = json.loads(d["trigger_phrases"])
    d["steps"] = json.loads(d["steps"])
    return d


@routines_router.delete("/{name}")
async def delete_routine(name: str):
    db.execute("DELETE FROM routines WHERE LOWER(name) = LOWER(?)", (name,))
    return {"deleted": name}


# ─── Settings ─────────────────────────────────────────────────────────────────

@settings_router.get("/")
async def get_settings():
    return {"settings": get_all_preferences()}


@settings_router.post("/{key}")
async def update_setting(key: str, body: dict):
    value = str(body.get("value", ""))
    set_preference(key, value)
    return {"key": key, "value": value}


@settings_router.get("/validate-aliases")
async def validate_aliases():
    learner = Learner()
    removed = learner.validate_aliases()
    return {"stale_aliases_removed": removed}


# ─── Personal Command Registry ────────────────────────────────────────────────

@commands_router.get("/")
async def list_all_commands():
    return {"commands": list_commands()}


@commands_router.get("/chrome-profiles")
async def chrome_profiles_endpoint(refresh: bool = False):
    profiles = discover_profiles() if refresh else get_cached_profiles()
    if not profiles:
        profiles = discover_profiles()
    return {"profiles": profiles}


@commands_router.post("/")
async def create_command(body: dict):
    """
    Create a custom command.
    Body: {trigger_phrase, targets:[{type,value}], browser, browser_profile_email, response_text}
    """
    command_id = save_command(
        trigger_phrase=body["trigger_phrase"],
        targets=body.get("targets", []),
        browser=body.get("browser", "default"),
        browser_profile_dir=body.get("browser_profile_dir", ""),
        browser_profile_email=body.get("browser_profile_email", ""),
        open_mode=body.get("open_mode", "tabs"),
        confirmation_mode=body.get("confirmation_mode", "none"),
        response_text=body.get("response_text", ""),
    )
    return {"id": command_id, "created": True}


@commands_router.get("/{command_id}")
async def get_command(command_id: str):
    row = db.fetchone("SELECT * FROM custom_commands WHERE id = ?", (command_id,))
    if not row:
        return {"error": "Not found"}
    targets = db.fetchall(
        "SELECT * FROM custom_command_targets WHERE command_id = ? ORDER BY launch_order",
        (command_id,),
    )
    return {**dict(row), "targets": [dict(t) for t in targets]}


@commands_router.delete("/{command_id}")
async def delete_command_endpoint(command_id: str):
    delete_command(command_id)
    return {"deleted": command_id}


@commands_router.post("/test/{command_id}")
async def test_command(command_id: str):
    """Trigger a custom command by ID for testing."""
    row = db.fetchone("SELECT trigger_phrase FROM custom_commands WHERE id = ?", (command_id,))
    if not row:
        return {"error": "Not found"}
    # The pipeline will handle execution when this comes in via /command
    return {"trigger_phrase": row["trigger_phrase"]}
