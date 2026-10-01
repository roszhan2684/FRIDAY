-- Migration 003 — VS Code in Coding Mode + new conversation tables

-- Coding Mode: VS Code + Terminal + Apple Music
UPDATE routines SET
    steps = '[
        {"tool": "open_app", "args": {"name": "Visual Studio Code"}, "spoken_before": "Opening VS Code.", "delay_seconds": 0},
        {"tool": "open_app", "args": {"name": "Terminal"}, "spoken_before": "And your terminal.", "delay_seconds": 1},
        {"tool": "open_app", "args": {"name": "Music"}, "spoken_before": "Getting your music going.", "delay_seconds": 1}
    ]',
    updated_at = datetime('now')
WHERE LOWER(name) = 'coding mode';

-- Conversation context table — stores multi-turn state
CREATE TABLE IF NOT EXISTS conversation_context (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    turn        INTEGER NOT NULL,
    role        TEXT NOT NULL,       -- 'user' | 'friday'
    content     TEXT NOT NULL,
    tool_called TEXT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ctx_session ON conversation_context(session_id, turn);

-- Learned follow-up patterns — tracks which commands lead to follow-up searches
CREATE TABLE IF NOT EXISTS followup_patterns (
    trigger_tool    TEXT NOT NULL,
    trigger_arg_key TEXT,
    trigger_arg_val TEXT,
    followup_tool   TEXT NOT NULL,
    count           INTEGER DEFAULT 1,
    PRIMARY KEY (trigger_tool, trigger_arg_val, followup_tool)
);
