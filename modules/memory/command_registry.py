"""Personal command registry — CRUD and lookup for user-defined trigger phrases.

Every custom command maps a trigger phrase → a list of targets (URLs, files, apps)
with optional browser profile context.
"""
from __future__ import annotations
import json
import re
import uuid
from datetime import datetime

from database import db


# ─── Normalization ────────────────────────────────────────────────────────────

def normalize(phrase: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = phrase.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


# ─── Lookup ───────────────────────────────────────────────────────────────────

def find_command(transcript: str) -> dict | None:
    """
    Look up a custom command by transcript.
    Uses exact normalized match first, then fuzzy substring match.
    Returns the full command dict with targets, or None.
    """
    norm = normalize(transcript)
    row = db.fetchone(
        "SELECT * FROM custom_commands WHERE normalized_trigger = ?", (norm,)
    )

    # Fuzzy: check if any stored trigger is contained in (or contains) transcript
    if not row:
        rows = db.fetchall("SELECT * FROM custom_commands")
        for r in rows:
            stored = r["normalized_trigger"]
            if stored in norm or norm in stored:
                row = r
                break

    if not row:
        return None

    targets = db.fetchall(
        "SELECT * FROM custom_command_targets WHERE command_id = ? ORDER BY launch_order",
        (row["id"],),
    )
    return {
        **dict(row),
        "targets": [dict(t) for t in targets],
    }


def list_commands() -> list[dict]:
    rows = db.fetchall(
        "SELECT id, trigger_phrase, browser, browser_profile_email, use_count, updated_at "
        "FROM custom_commands ORDER BY use_count DESC"
    )
    result = []
    for r in rows:
        d = dict(r)
        targets = db.fetchall(
            "SELECT target_type, target_value FROM custom_command_targets WHERE command_id = ? ORDER BY launch_order",
            (r["id"],),
        )
        d["targets"] = [dict(t) for t in targets]
        result.append(d)
    return result


# ─── Create / Update ──────────────────────────────────────────────────────────

def save_command(
    trigger_phrase: str,
    targets: list[dict],              # [{type, value, order?, delay?}]
    browser: str = "default",
    browser_profile_dir: str = "",
    browser_profile_email: str = "",
    open_mode: str = "tabs",
    confirmation_mode: str = "none",
    response_text: str = "",
) -> str:
    """
    Create or replace a custom command.
    Returns the command id.
    """
    norm = normalize(trigger_phrase)
    spoken = response_text or f"On it, Boss."

    existing = db.fetchone(
        "SELECT id FROM custom_commands WHERE normalized_trigger = ?", (norm,)
    )
    command_id = existing["id"] if existing else str(uuid.uuid4())

    db.execute(
        """INSERT INTO custom_commands
           (id, trigger_phrase, normalized_trigger, browser, browser_profile_dir,
            browser_profile_email, open_mode, confirmation_mode, response_text, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))
           ON CONFLICT(normalized_trigger) DO UPDATE SET
               trigger_phrase=excluded.trigger_phrase,
               browser=excluded.browser,
               browser_profile_dir=excluded.browser_profile_dir,
               browser_profile_email=excluded.browser_profile_email,
               open_mode=excluded.open_mode,
               confirmation_mode=excluded.confirmation_mode,
               response_text=excluded.response_text,
               updated_at=datetime('now')""",
        (command_id, trigger_phrase, norm, browser, browser_profile_dir,
         browser_profile_email, open_mode, confirmation_mode, spoken),
    )

    # Replace all targets
    db.execute("DELETE FROM custom_command_targets WHERE command_id = ?", (command_id,))
    for i, t in enumerate(targets):
        db.execute(
            """INSERT INTO custom_command_targets
               (id, command_id, target_type, target_value, launch_order, delay_seconds)
               VALUES (?,?,?,?,?,?)""",
            (str(uuid.uuid4()), command_id,
             t.get("type", "url"), t["value"],
             t.get("order", i), t.get("delay", 0.5)),
        )

    return command_id


def delete_command(command_id: str) -> None:
    db.execute("DELETE FROM custom_commands WHERE id = ?", (command_id,))


def increment_use(command_id: str) -> None:
    db.execute(
        "UPDATE custom_commands SET use_count = use_count + 1, updated_at = datetime('now') WHERE id = ?",
        (command_id,),
    )


# ─── Setup session helpers ────────────────────────────────────────────────────

class SetupSession:
    """
    Tracks the state of a guided setup conversation for a new custom command.
    One session per trigger phrase, lives in memory during the conversation.
    """

    STEPS = ["ASKING_TARGETS", "ASKING_BROWSER", "ASKING_PROFILE", "ASKING_FILES", "DONE"]

    def __init__(self, trigger_phrase: str):
        self.trigger_phrase = trigger_phrase
        self.step = "ASKING_TARGETS"
        self.targets: list[dict] = []
        self.browser = "default"
        self.profile_dir = ""
        self.profile_email = ""
        self.pending_urls: list[str] = []

    @property
    def is_done(self) -> bool:
        return self.step == "DONE"

    def next_question(self, chrome_profiles: list[dict] | None = None) -> str:
        if self.step == "ASKING_TARGETS":
            return (
                "What sites or apps should I open, Boss? "
                "Say each one, then say 'done' when finished."
            )
        if self.step == "ASKING_BROWSER":
            return "Which browser should I use — Chrome or Safari, Boss?"
        if self.step == "ASKING_PROFILE":
            if chrome_profiles:
                options = ", ".join(
                    f"{p['email'] or p['display_name']}"
                    for p in chrome_profiles[:4]
                )
                return f"Which Chrome account, Boss? I found: {options}."
            return "Which Chrome account email should I use, Boss?"
        if self.step == "ASKING_FILES":
            return "Should I also open any files or folders, Boss? Say 'no' to skip."
        return ""

    def feed(self, text: str) -> None:
        """Process user input for the current step."""
        t = text.lower().strip()

        if self.step == "ASKING_TARGETS":
            if t in ("done", "that's it", "thats it", "finish", "finished", "stop"):
                self.step = "ASKING_BROWSER"
            else:
                # Detect URL vs app
                target_type = "url" if ("." in t and " " not in t) or t.startswith("http") else "app"
                value = text.strip()
                if target_type == "url" and not value.startswith("http"):
                    value = "https://" + value
                self.targets.append({"type": target_type, "value": value})

        elif self.step == "ASKING_BROWSER":
            if "chrome" in t:
                self.browser = "chrome"
                self.step = "ASKING_PROFILE"
            else:
                self.browser = "safari" if "safari" in t else "default"
                self.step = "ASKING_FILES"

        elif self.step == "ASKING_PROFILE":
            # Store whatever the user said as the profile identifier (email or name)
            self.profile_email = text.strip()
            self.step = "ASKING_FILES"

        elif self.step == "ASKING_FILES":
            if t not in ("no", "nope", "skip", "none", "no thanks"):
                # Treat as a file or folder path hint
                self.targets.append({"type": "file", "value": text.strip()})
            self.step = "DONE"

    def to_save_args(self) -> dict:
        spoken = f"Opening your {self.trigger_phrase} setup"
        if self.profile_email:
            spoken += f" in Chrome ({self.profile_email})"
        spoken += ", Boss."
        return {
            "trigger_phrase": self.trigger_phrase,
            "targets": self.targets,
            "browser": self.browser,
            "browser_profile_email": self.profile_email,
            "open_mode": "tabs",
            "response_text": spoken,
        }
