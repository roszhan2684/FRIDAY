-- FRIDAY Database Schema — Migration 001

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─── Interaction Events ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS interaction_events (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    transcript      TEXT NOT NULL,
    audio_hash      TEXT,
    confidence      REAL,
    tool_called     TEXT,
    tool_args       TEXT,           -- JSON
    spoken_response TEXT,
    outcome         TEXT NOT NULL DEFAULT 'success',
    error           TEXT,
    duration_ms     INTEGER DEFAULT 0,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ie_timestamp ON interaction_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_ie_tool ON interaction_events(tool_called);

-- Full-text search on transcripts
CREATE VIRTUAL TABLE IF NOT EXISTS interaction_fts
    USING fts5(transcript, content='interaction_events', content_rowid='rowid');

-- ─── Correction Logs ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS correction_logs (
    id              TEXT PRIMARY KEY,
    audio_hash      TEXT NOT NULL,
    bad_transcript  TEXT NOT NULL,
    corrected_text  TEXT NOT NULL,
    used_in_training INTEGER DEFAULT 0,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── Learned Aliases ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS learned_aliases (
    phrase          TEXT PRIMARY KEY,
    resolved_path   TEXT NOT NULL,
    file_type       TEXT DEFAULT '',
    confidence      REAL DEFAULT 1.0,
    use_count       INTEGER DEFAULT 1,
    last_used       TEXT NOT NULL DEFAULT (datetime('now')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── User Preferences ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS preferences (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── Routines ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS routines (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    trigger_phrases TEXT NOT NULL,  -- JSON array
    steps           TEXT NOT NULL,  -- JSON array of RoutineStep
    use_count       INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── File References ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS file_references (
    path            TEXT PRIMARY KEY,
    alias           TEXT,
    open_count      INTEGER DEFAULT 0,
    last_opened     TEXT,
    tags            TEXT DEFAULT '[]'  -- JSON array
);

-- ─── Routine Suggestions (from pattern detection) ────────────────────────────

CREATE TABLE IF NOT EXISTS routine_suggestions (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    steps           TEXT NOT NULL,  -- JSON
    trigger_count   INTEGER DEFAULT 1,
    accepted        INTEGER,        -- NULL = pending, 1 = accepted, 0 = rejected
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── Audit Log ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action          TEXT NOT NULL,
    tool            TEXT,
    args            TEXT,           -- JSON
    confirmed       INTEGER DEFAULT 0,
    timestamp       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ─── Model Registry ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS model_versions (
    component       TEXT PRIMARY KEY,   -- 'wake', 'stt', 'llm', 'tts', 'embed'
    model_id        TEXT NOT NULL,
    version         TEXT,
    deployed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    notes           TEXT
);

-- ─── Seed Data ───────────────────────────────────────────────────────────────

INSERT OR IGNORE INTO preferences(key, value) VALUES
    ('tts_voice', 'Samantha'),
    ('tts_rate', '185'),
    ('confidence_threshold', '0.75'),
    ('confirm_risky_actions', 'true'),
    ('learning_enabled', 'true');

INSERT OR IGNORE INTO model_versions(component, model_id, version, notes) VALUES
    ('wake', 'openwakeword/hey_mycroft', 'v0.1', 'placeholder until hey_friday trained'),
    ('stt', 'mlx-community/whisper-medium-mlx', 'v0.1', 'Metal-accelerated'),
    ('llm', 'llama3.2:3b', 'v0.1', 'via Ollama'),
    ('tts', 'macos/samantha', 'native', 'macOS built-in neural voice');

-- Prebuilt routines
INSERT OR IGNORE INTO routines(id, name, trigger_phrases, steps) VALUES
(
    'routine-morning',
    'Morning Mode',
    '["morning mode", "good morning", "start my day"]',
    '[
        {"tool": "open_app", "args": {"name": "Calendar"}, "spoken_before": "Good morning, Boss. Opening your calendar.", "delay_seconds": 0},
        {"tool": "open_app", "args": {"name": "Mail"}, "spoken_before": "Checking your mail.", "delay_seconds": 1},
        {"tool": "open_url", "args": {"url": "https://news.ycombinator.com"}, "spoken_before": "Pulling up Hacker News.", "delay_seconds": 1}
    ]'
),
(
    'routine-coding',
    'Coding Mode',
    '["coding mode", "let us code", "start coding"]',
    '[
        {"tool": "open_app", "args": {"name": "Cursor"}, "spoken_before": "Opening Cursor.", "delay_seconds": 0},
        {"tool": "open_app", "args": {"name": "Terminal"}, "spoken_before": "And your terminal.", "delay_seconds": 1},
        {"tool": "open_app", "args": {"name": "Spotify"}, "spoken_before": "Getting your music going.", "delay_seconds": 1}
    ]'
),
(
    'routine-jobhunt',
    'Job Hunt Mode',
    '["job hunt mode", "job hunting", "job search mode"]',
    '[
        {"tool": "open_url", "args": {"url": "https://linkedin.com/jobs"}, "spoken_before": "Opening LinkedIn Jobs.", "delay_seconds": 0},
        {"tool": "open_file", "args": {"query": "resume"}, "spoken_before": "Pulling up your resume.", "delay_seconds": 1},
        {"tool": "open_app", "args": {"name": "Mail"}, "spoken_before": "And your mail for follow-ups.", "delay_seconds": 1}
    ]'
),
(
    'routine-interview',
    'Interview Mode',
    '["interview mode", "prep for interview", "interview prep"]',
    '[
        {"tool": "respond_only", "args": {"message": "Interview mode activated. You have got this, Boss."}, "spoken_before": "", "delay_seconds": 0},
        {"tool": "open_app", "args": {"name": "Notes"}, "spoken_before": "Opening Notes for quick jotting.", "delay_seconds": 1},
        {"tool": "open_url", "args": {"url": "https://leetcode.com"}, "spoken_before": "And LeetCode, just in case.", "delay_seconds": 1}
    ]'
);
