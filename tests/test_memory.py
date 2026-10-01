"""Tests for the memory store and learner — uses a temp SQLite DB."""
import os
import pytest
import tempfile
from unittest.mock import patch

# Point DB at a temp file before any imports touch the real DB
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

with patch.dict(os.environ, {"FRIDAY_DB_PATH": _tmp_db.name}):
    from database.db import init_db, DB_PATH
    from modules.memory.store import (
        upsert_alias, get_alias, get_all_aliases,
        set_preference, get_preference,
        log_interaction,
    )
    from shared.schemas import InteractionEvent, OutcomeStatus


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    import database.db as db_module
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    init_db()
    yield
    if db_path.exists():
        db_path.unlink()


def test_alias_roundtrip():
    upsert_alias("resume", "/Users/test/resume.pdf")
    assert get_alias("resume") == "/Users/test/resume.pdf"


def test_alias_case_insensitive():
    upsert_alias("Resume", "/Users/test/resume.pdf")
    assert get_alias("resume") == "/Users/test/resume.pdf"
    assert get_alias("RESUME") == "/Users/test/resume.pdf"


def test_alias_use_count_increments():
    from database import db
    upsert_alias("portfolio", "/Users/test/portfolio.pdf")
    upsert_alias("portfolio", "/Users/test/portfolio.pdf")
    row = db.fetchone("SELECT use_count FROM learned_aliases WHERE phrase = 'portfolio'")
    assert row["use_count"] == 2


def test_preference_roundtrip():
    set_preference("tts_voice", "Alex")
    assert get_preference("tts_voice") == "Alex"


def test_preference_default():
    assert get_preference("nonexistent_key", "default_val") == "default_val"


def test_log_interaction():
    event = InteractionEvent(
        session_id="test-session",
        transcript="open spotify",
        tool_called="open_app",
        tool_args={"name": "Spotify"},
        spoken_response="Opening Spotify, Boss.",
        outcome=OutcomeStatus.SUCCESS,
    )
    log_interaction(event)

    from database import db
    row = db.fetchone("SELECT * FROM interaction_events WHERE id = ?", (event.id,))
    assert row is not None
    assert row["transcript"] == "open spotify"
    assert row["tool_called"] == "open_app"
