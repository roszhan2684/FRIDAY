-- Migration 005 — Reminders, Shopping Lists, Errands, Calendar Cache

-- ─── Reminders ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS reminders (
    id              TEXT PRIMARY KEY,
    text            TEXT NOT NULL,          -- "Go to Target and buy avocados"
    raw_input       TEXT,                   -- what the user actually said
    due_at          TEXT,                   -- ISO8601 datetime
    place           TEXT,                   -- "Target", "home", etc.
    category        TEXT DEFAULT 'general', -- 'errand'|'task'|'event_prep'|'general'
    status          TEXT DEFAULT 'pending', -- 'pending'|'fired'|'snoozed'|'done'|'dismissed'
    snoozed_until   TEXT,
    fired_at        TEXT,
    follow_up_action TEXT,                  -- JSON: action to offer when fired
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rem_due ON reminders(due_at, status);
CREATE INDEX IF NOT EXISTS idx_rem_status ON reminders(status);

-- ─── Shopping List ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS shopping_items (
    id          TEXT PRIMARY KEY,
    item        TEXT NOT NULL,
    store       TEXT,                   -- "Target", "Trader Joe's", etc.
    quantity    TEXT,                   -- "2 avocados", "a dozen"
    category    TEXT,                   -- "produce", "dairy", etc.
    checked     INTEGER DEFAULT 0,
    added_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── Errands ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS errands (
    id          TEXT PRIMARY KEY,
    text        TEXT NOT NULL,
    place       TEXT,
    due_hint    TEXT,                   -- "tonight", "this weekend"
    status      TEXT DEFAULT 'pending', -- 'pending'|'done'
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── Calendar Event Cache ─────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS calendar_events_cache (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    start_time      TEXT NOT NULL,      -- ISO8601
    end_time        TEXT NOT NULL,
    calendar_name   TEXT,
    location        TEXT,
    url             TEXT,               -- meeting link if present
    all_day         INTEGER DEFAULT 0,
    cached_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cal_start ON calendar_events_cache(start_time);

-- ─── Proactive Suggestion Log ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS proactive_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,      -- 'meeting_alert'|'reminder_fire'|'routine_suggestion'
    payload     TEXT,               -- JSON
    accepted    INTEGER,            -- NULL=shown but no response, 1=yes, 0=no
    shown_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── Briefing preferences ─────────────────────────────────────────────────────

INSERT OR IGNORE INTO preferences(key, value) VALUES
    ('briefing_weather', 'true'),
    ('briefing_calendar', 'true'),
    ('briefing_reminders', 'true'),
    ('briefing_greeting', 'true'),
    ('proactive_enabled', 'true'),
    ('proactive_meeting_threshold_minutes', '10'),
    ('weather_location', 'auto'),
    ('wake_mode', 'acknowledgment');   -- 'silent'|'acknowledgment'|'briefing'
