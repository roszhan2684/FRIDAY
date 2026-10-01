-- Migration 004 — Personal Command Registry
-- Stores user-defined trigger phrases → action bundles with full context

-- ─── Custom Commands ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS custom_commands (
    id                  TEXT PRIMARY KEY,
    trigger_phrase      TEXT NOT NULL,              -- raw phrase the user says
    normalized_trigger  TEXT NOT NULL UNIQUE,       -- lowercased + stripped
    intent_type         TEXT NOT NULL DEFAULT 'open_targets',
    routine_name        TEXT,                       -- if linking to an existing routine
    browser             TEXT DEFAULT 'default',    -- 'chrome' | 'safari' | 'default'
    browser_profile_dir TEXT,                      -- Chrome profile dir e.g. 'Profile 3'
    browser_profile_email TEXT,                    -- display label e.g. 'roszhan.2684@gmail.com'
    open_mode           TEXT DEFAULT 'tabs',       -- 'tabs' | 'windows'
    confirmation_mode   TEXT DEFAULT 'none',       -- 'none' | 'ask' | 'ask_always'
    response_text       TEXT,                      -- spoken response when triggered
    use_count           INTEGER DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cc_normalized ON custom_commands(normalized_trigger);

-- ─── Custom Command Targets ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS custom_command_targets (
    id              TEXT PRIMARY KEY,
    command_id      TEXT NOT NULL REFERENCES custom_commands(id) ON DELETE CASCADE,
    target_type     TEXT NOT NULL,      -- 'url' | 'file' | 'folder' | 'app'
    target_value    TEXT NOT NULL,      -- the actual URL/path/app name
    launch_order    INTEGER DEFAULT 0,
    delay_seconds   REAL DEFAULT 0.5,
    open_mode       TEXT DEFAULT 'tab'  -- 'tab' | 'window' | 'default'
);

CREATE INDEX IF NOT EXISTS idx_cct_command ON custom_command_targets(command_id, launch_order);

-- ─── Chrome Profiles Cache ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS chrome_profiles (
    profile_dir     TEXT PRIMARY KEY,   -- 'Default' | 'Profile 1' | 'Profile 3' etc.
    display_name    TEXT,               -- user-visible name
    email           TEXT,               -- Google account email
    last_seen       TEXT NOT NULL DEFAULT (datetime('now'))
);
